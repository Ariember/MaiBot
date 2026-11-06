"""GHCR 镜像检查与文件队列；Docker 权限只属于容器外的执行器。"""

from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import hashlib
import json
import os
import re
import time
import uuid

from .update_errors import SelfUpdateError

IMAGE_REPOSITORY = "ghcr.io/ariember/maibot"
IMAGE_PAGE = "https://github.com/Ariember/MaiBot/pkgs/container/maibot"
DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")
CHANNELS = ("latest", "dev")
STATUS_MAX_AGE = 90
REQUEST_MAX_AGE = 600


def image_install() -> bool:
    return os.environ.get("MAIBOT_CONTAINER_IMAGE") == "1"


def image_channel() -> str:
    channel = os.environ.get("MAIBOT_IMAGE_CHANNEL", "latest")
    if channel not in CHANNELS:
        raise SelfUpdateError("invalid_source", "镜像更新渠道只能是 latest 或 dev")
    return channel


def write_json(path: Path, payload: Dict[str, Any], *, exclusive: bool = False) -> None:
    """完整写入后再发布；独占发布防止重复请求覆盖正在排队的目标。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as output:
            json.dump(payload, output, ensure_ascii=False)
            output.flush()
            os.fsync(output.fileno())
        if exclusive:
            os.link(temporary, path)
        else:
            os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_status(directory: Path) -> Dict[str, Any]:
    try:
        status = json.loads((directory / "image-status.json").read_text(encoding="utf-8"))
        age = time.time() - status["updated_at"]
        if not 0 <= age <= STATUS_MAX_AGE or status["channel"] != image_channel():
            raise ValueError("更新服务状态过期或渠道不一致")
        if not DIGEST_PATTERN.fullmatch(status.get("digest", "")):
            raise ValueError("当前镜像摘要无效")
        return status
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SelfUpdateError("image_updater_unavailable", "镜像更新服务未就绪，请检查 updater 容器日志") from exc


def update_blocker(directory: Path) -> Optional[str]:
    if (directory / "image-recovery.json").exists():
        return "image_recovery_required"
    if any((directory / name).exists() for name in ("image-pending.json", "image-active.json")):
        return "image_update_busy"
    return None


def fetch_digest(channel: str) -> str:
    """只访问本 fork 的公开 GHCR 包；匿名令牌不写磁盘或日志。"""
    if channel not in CHANNELS:
        raise SelfUpdateError("invalid_source", "镜像更新渠道只能是 latest 或 dev")
    repository = IMAGE_REPOSITORY.removeprefix("ghcr.io/")
    query = urlencode({"service": "ghcr.io", "scope": f"repository:{repository}:pull"})
    try:
        with urlopen(f"https://ghcr.io/token?{query}", timeout=15) as response:
            token = json.load(response)["token"]
        request = Request(
            f"https://ghcr.io/v2/{repository}/manifests/{channel}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": ", ".join(
                    (
                        "application/vnd.oci.image.index.v1+json",
                        "application/vnd.docker.distribution.manifest.list.v2+json",
                        "application/vnd.oci.image.manifest.v1+json",
                        "application/vnd.docker.distribution.manifest.v2+json",
                    )
                ),
            },
        )
        with urlopen(request, timeout=30) as response:
            body = response.read(4 * 1024 * 1024 + 1)
            digest = response.headers.get("Docker-Content-Digest", "")
        if len(body) > 4 * 1024 * 1024 or not DIGEST_PATTERN.fullmatch(digest):
            raise ValueError("无效的镜像清单摘要")
        if digest != f"sha256:{hashlib.sha256(body).hexdigest()}":
            raise ValueError("镜像清单摘要校验失败")
        return digest
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SelfUpdateError("fetch_failed", "无法读取 GHCR 镜像；请确认包已公开且 ghcr.io 可访问") from exc


def request_image_update(directory: Path, target: str) -> Dict[str, Any]:
    if not DIGEST_PATTERN.fullmatch(target):
        raise SelfUpdateError("invalid_commit", "目标必须是完整的 SHA-256 镜像摘要")
    status = read_status(directory)
    blocker = update_blocker(directory)
    if blocker:
        raise SelfUpdateError(blocker, "已有镜像更新任务，或上次更新需要人工恢复")
    if target == status["digest"]:
        raise SelfUpdateError("already_up_to_date", "当前已经是这个镜像")
    if target != fetch_digest(image_channel()):
        raise SelfUpdateError("state_changed", "镜像渠道已变化，请重新检查更新")
    pending = {
        "target_commit": target,
        "base_commit": status["digest"],
        "branch": image_channel(),
        "requested_at": time.time(),
        "source_id": "ghcr",
        "custom_prefix": "",
    }
    try:
        write_json(directory / "image-pending.json", pending, exclusive=True)
    except FileExistsError as exc:
        raise SelfUpdateError("image_update_busy", "已有镜像更新请求，请等待完成") from exc
    return pending
