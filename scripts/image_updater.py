"""Compose 镜像更新服务；只接受本 fork 镜像摘要，不开放网络控制接口。"""

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List
import argparse
import json
import logging
import os
import shutil
import subprocess
import time

from src.common.image_update import (
    DIGEST_PATTERN,
    IMAGE_REPOSITORY,
    REQUEST_MAX_AGE,
    fetch_digest,
    image_channel,
    write_json,
)
from src.common.instance_lock import FileLock
from src.common.self_update import UpdateResult
from src.common.update_errors import SelfUpdateError

logger = logging.getLogger("image_updater")
CORE_CONTAINER = "maim-bot-core"


def run(command: List[str], *, timeout: int = 1800) -> str:
    completed = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
    if completed.returncode:
        raise RuntimeError(f"{command[0]} {command[1]} 失败（{completed.returncode}）：{completed.stderr[-2000:]}")
    return completed.stdout


class ImageUpdater:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve(strict=True)
        self.state = self.root / "docker-update-state"
        self.override = self.root / "docker-compose.override.yml"
        self.channel = image_channel()
        self.project = ""

    def inspect(self) -> Dict[str, Any]:
        container = json.loads(run(["docker", "inspect", CORE_CONTAINER], timeout=30))[0]
        labels = container["Config"]["Labels"]
        if labels.get("com.docker.compose.service") != "core":
            raise ValueError("目标容器不是 Compose core 服务")
        if Path(labels["com.docker.compose.project.working_dir"]).resolve() != self.root:
            raise ValueError("部署目录与 core 的 Compose 工作目录不一致")
        allowed = {str(self.root / "docker-compose.yml"), str(self.override)}
        if not set(labels["com.docker.compose.project.config_files"].split(",")) <= allowed:
            raise ValueError("存在额外的 Compose 配置文件，请手动更新，避免丢失部署参数")
        self.project = labels["com.docker.compose.project"]
        return container

    def compose(self, *arguments: str) -> str:
        files = ["--file", str(self.root / "docker-compose.yml")]
        if self.override.exists():
            files.extend(["--file", str(self.override)])
        return run(
            [
                "docker",
                "compose",
                "--project-directory",
                str(self.root),
                "--project-name",
                self.project,
                *files,
                *arguments,
            ]
        )

    def current_digest(self, container: Dict[str, Any]) -> str:
        image = json.loads(run(["docker", "image", "inspect", container["Image"]], timeout=30))[0]
        prefix = IMAGE_REPOSITORY + "@"
        references = image.get("RepoDigests") or []
        configured = container["Config"]["Image"]
        if configured.startswith(prefix) and configured in references:
            references = [configured]
        for reference in references:
            if reference.startswith(prefix) and DIGEST_PATTERN.fullmatch(reference[len(prefix) :]):
                return reference[len(prefix) :]
        raise ValueError("core 尚未运行本 fork 的 GHCR 镜像，请先按部署文档迁移")

    def publish_status(self) -> None:
        container = self.inspect()
        write_json(
            self.state / "image-status.json",
            {
                "digest": self.current_digest(container),
                "channel": self.channel,
                "updated_at": time.time(),
            },
        )

    def pin_image(self, digest: str) -> None:
        if not DIGEST_PATTERN.fullmatch(digest):
            raise ValueError("无效的镜像摘要")
        write_json(self.override, {"services": {"core": {"image": f"{IMAGE_REPOSITORY}@{digest}"}}})

    def validate_override(self) -> None:
        if not self.override.exists():
            return
        try:
            existing = json.loads(self.override.read_text(encoding="utf-8"))
            image = existing["services"]["core"]["image"]
            if existing != {"services": {"core": {"image": image}}}:
                raise ValueError("override 包含自定义配置")
            if not image.startswith(IMAGE_REPOSITORY + "@") or not DIGEST_PATTERN.fullmatch(image.split("@", 1)[1]):
                raise ValueError("override 不是本 fork 镜像")
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError("docker-compose.override.yml 保留给镜像更新器；请将自定义配置合入主 Compose 文件") from exc

    def data_paths(self, container: Dict[str, Any]) -> List[Path]:
        paths: List[Path] = []
        for mount in container["Mounts"]:
            if mount["Destination"] == "/MaiMBot/data/self_update":
                if Path(mount["Source"]).resolve() != self.state:
                    raise ValueError("更新状态目录挂载不一致")
                continue
            if mount["Type"] != "bind":
                raise ValueError("自动备份只支持部署目录内的 bind mounts，请手动处理额外卷")
            source = Path(mount["Source"]).resolve(strict=True)
            if not source.is_relative_to(self.root) or source == self.root:
                raise ValueError("持久数据必须位于部署目录内，不能直接挂载部署根目录")
            if source.is_relative_to(self.root / "docker-backups") or source == self.state:
                raise ValueError("不能把更新器状态或备份目录用作业务数据")
            paths.append(source)
        # data 内的插件、表情、日志挂载只备份一次。
        return [
            path
            for path in sorted(set(paths))
            if not any(path != parent and path.is_relative_to(parent) for parent in paths)
        ]

    def save_backup(self, paths: List[Path], backup: Path, digest: str) -> None:
        backup.mkdir(parents=True, mode=0o700)
        for source in paths:
            destination = backup / "files" / source.relative_to(self.root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, destination, symlinks=True)
            else:
                shutil.copy2(source, destination)
        write_json(
            backup / "manifest.json",
            {
                "digest": digest,
                "paths": [str(path.relative_to(self.root)) for path in paths],
            },
        )

    def start_core(self) -> None:
        self.compose(
            "up", "-d", "--no-deps", "--no-build", "--pull", "never", "--wait", "--wait-timeout", "300", "core"
        )

    def execute(self, pending: Dict[str, Any]) -> UpdateResult:
        result = UpdateResult(
            success=False, started_at=time.time(), source_name="GitHub Container Registry", stage="precheck"
        )
        stopped = False
        launched = False
        old_digest = ""
        try:
            container = self.inspect()
            old_digest = self.current_digest(container)
            target = pending["target_commit"]
            if not isinstance(target, str) or not DIGEST_PATTERN.fullmatch(target):
                raise ValueError("无效的目标镜像摘要")
            result.from_commit, result.to_commit = old_digest, target
            result.branch = self.channel
            result.from_version = container["Config"]["Labels"].get("org.opencontainers.image.version", "")
            if (
                pending["base_commit"] != old_digest
                or pending["branch"] != self.channel
                or pending["source_id"] != "ghcr"
            ):
                raise ValueError("当前镜像或渠道已变化，请重新检查更新")
            if not 0 <= time.time() - pending["requested_at"] <= REQUEST_MAX_AGE:
                raise ValueError("镜像更新请求已过期")
            if target == old_digest or target != fetch_digest(self.channel):
                raise ValueError("目标不再是当前渠道的新镜像，请重新检查更新")
            self.validate_override()
            paths = self.data_paths(container)
            result.stage = "pull"
            run(["docker", "pull", f"{IMAGE_REPOSITORY}@{target}"])
            image = json.loads(run(["docker", "image", "inspect", f"{IMAGE_REPOSITORY}@{target}"]))[0]
            if image["Config"].get("Healthcheck", {}).get("Test", ["NONE"])[0] == "NONE":
                raise ValueError("目标镜像缺少健康检查，拒绝自动替换")
            result.to_version = image["Config"]["Labels"].get("org.opencontainers.image.version", "")
            result.stage = "backup"
            stopped = True
            self.compose("stop", "--timeout", "70", "core")
            if self.inspect()["State"]["Running"]:
                raise RuntimeError("core 未停止，不能备份正在写入的数据")
            backup = self.root / "docker-backups" / f"{time.time_ns()}-{old_digest[7:19]}"
            self.save_backup(paths, backup, old_digest)
            result.backup_path = str(backup)
            self.pin_image(target)
            result.stage = "health"
            # 在启动前保存恢复信息；执行器自身中断时不盲目重复迁移。
            write_json(self.state / "last_result.json", asdict(result))
            launched = True
            self.start_core()
            if self.current_digest(self.inspect()) != target:
                raise RuntimeError("启动后的镜像摘要与确认目标不一致")
            result.success = True
            result.stage = "done"
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            RuntimeError,
            SelfUpdateError,
            subprocess.SubprocessError,
        ) as exc:
            result.error_code = "image_update_failed"
            result.error = str(exc)
            if stopped and not launched:
                try:
                    self.pin_image(old_digest)
                    self.start_core()
                    result.rolled_back = True
                except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as rollback_error:
                    result.rollback_error = str(rollback_error)
            elif launched:
                # 新程序可能已经迁移数据库；保留现场与备份，不能只切回旧代码。
                try:
                    self.compose("stop", "--timeout", "70", "core")
                except (OSError, RuntimeError, subprocess.SubprocessError) as stop_error:
                    result.rollback_error = str(stop_error)
                result.error += (
                    f"；新程序可能已迁移数据，请按 docs/docker-deployment.md 从备份恢复：{result.backup_path}"
                )
            if launched or result.rollback_error:
                write_json(self.state / "image-recovery.json", asdict(result))
        result.finished_at = time.time()
        write_json(self.state / "last_result.json", asdict(result))
        logger.info(
            "镜像更新结束：success=%s stage=%s backup=%s error=%s",
            result.success,
            result.stage,
            result.backup_path,
            result.error,
        )
        return result

    def restore(self, backup: Path) -> None:
        """显式恢复完整快照，同时保存失败后的数据供人工核对。"""
        backup = backup.resolve(strict=True)
        if not backup.is_relative_to(self.root / "docker-backups"):
            raise ValueError("只能恢复当前部署目录 docker-backups 内的快照")
        manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
        digest = manifest["digest"]
        if not DIGEST_PATTERN.fullmatch(digest):
            raise ValueError("备份中的镜像摘要无效")
        container = self.inspect()
        allowed = set(self.data_paths(container))
        paths = [(self.root / value).resolve() for value in manifest["paths"]]
        if not paths or set(paths) != allowed:
            raise ValueError("备份路径与当前持久数据挂载不一致，拒绝覆盖")
        for path in paths:
            saved = backup / "files" / path.relative_to(self.root)
            if not saved.exists() or saved.is_symlink():
                raise ValueError("备份不完整或包含不安全的根路径")
        self.validate_override()
        run(["docker", "image", "inspect", f"{IMAGE_REPOSITORY}@{digest}"])
        with FileLock(self.state / "executor.lock"):
            self.compose("stop", "--timeout", "70", "core")
            preserved = backup / f"after-failure-{time.time_ns()}"
            for path in paths:
                relative = path.relative_to(self.root)
                saved = backup / "files" / relative
                destination = preserved / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                if path.is_dir():
                    destination.mkdir()
                    # 保留 bind mount 根目录本身，避免其他容器继续引用已被改名的目录。
                    for child in path.iterdir():
                        shutil.move(str(child), str(destination / child.name))
                    shutil.copytree(saved, path, dirs_exist_ok=True, symlinks=True)
                else:
                    shutil.move(str(path), str(destination))
                    shutil.copy2(saved, path)
            self.pin_image(digest)
            self.start_core()
            result = UpdateResult(
                success=False,
                rolled_back=True,
                started_at=time.time(),
                finished_at=time.time(),
                to_commit=digest,
                stage="restored",
                source_name="GitHub Container Registry",
                backup_path=str(backup),
                error=f"已从备份恢复；失败后的数据保存在 {preserved}",
            )
            write_json(self.state / "last_result.json", asdict(result))
            for name in ("image-recovery.json", "image-active.json", "image-pending.json"):
                (self.state / name).unlink(missing_ok=True)
            self.publish_status()

    def serve(self) -> None:
        self.state.mkdir(parents=True, exist_ok=True)
        active = self.state / "image-active.json"
        pending = self.state / "image-pending.json"
        with FileLock(self.state / "executor.lock"):
            if active.exists():
                write_json(
                    self.state / "image-recovery.json",
                    {
                        "error": "更新执行器在任务中中断，请检查 last_result.json、备份和容器状态后手动恢复",
                    },
                )
            while True:
                try:
                    self.publish_status()
                    if pending.exists() and not active.exists() and not (self.state / "image-recovery.json").exists():
                        pending.replace(active)
                        try:
                            payload = json.loads(active.read_text(encoding="utf-8"))
                            if not isinstance(payload, dict):
                                raise ValueError("更新请求不是对象")
                            self.execute(payload)
                        except (OSError, ValueError) as exc:
                            write_json(self.state / "image-recovery.json", {"error": str(exc)})
                            logger.error("无法读取更新请求：%s", exc)
                        else:
                            active.unlink()
                except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as exc:
                    logger.error("镜像更新服务未就绪：%s", exc)
                time.sleep(5)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restore", type=Path, help="停止 updater 服务后，从指定备份恢复数据与镜像")
    arguments = parser.parse_args()
    updater = ImageUpdater(Path(os.environ["MAIBOT_DEPLOY_DIR"]))
    if arguments.restore:
        updater.restore(arguments.restore)
    else:
        updater.serve()
