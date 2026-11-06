from pathlib import Path
from unittest.mock import Mock
import hashlib
import json
import time

import pytest

from scripts import docker_healthcheck, image_updater
from src.common import image_update, self_update
from src.common.instance_lock import FileLock, register_instance
from src.common.update_errors import SelfUpdateError

OLD = "sha256:" + "1" * 64
NEW = "sha256:" + "2" * 64


def status(directory: Path, **changes):
    payload = {"digest": OLD, "channel": "latest", "updated_at": time.time(), **changes}
    image_update.write_json(directory / "image-status.json", payload)


@pytest.fixture(autouse=True)
def channel(monkeypatch):
    monkeypatch.setenv("MAIBOT_IMAGE_CHANNEL", "latest")
    monkeypatch.delenv("MAIBOT_CONTAINER_IMAGE", raising=False)


def test_queue_is_atomic_and_does_not_overwrite(tmp_path, monkeypatch):
    status(tmp_path)
    monkeypatch.setattr(image_update, "fetch_digest", lambda _: NEW)
    pending = image_update.request_image_update(tmp_path, NEW)
    assert pending["base_commit"] == OLD
    assert json.loads((tmp_path / "image-pending.json").read_text()) == pending
    with pytest.raises(SelfUpdateError, match="已有镜像更新"):
        image_update.request_image_update(tmp_path, NEW)
    with pytest.raises(FileExistsError):
        image_update.write_json(tmp_path / "image-pending.json", {}, exclusive=True)
    assert not list(tmp_path.glob(".*.tmp"))


@pytest.mark.parametrize("target", ["latest", "sha256:123", NEW + "\n", "--privileged", "other/image@" + NEW])
def test_invalid_target_never_contacts_registry(tmp_path, monkeypatch, target):
    fetch = Mock()
    monkeypatch.setattr(image_update, "fetch_digest", fetch)
    with pytest.raises(SelfUpdateError, match="完整的 SHA-256"):
        image_update.request_image_update(tmp_path, target)
    fetch.assert_not_called()


@pytest.mark.parametrize("changes", [{"updated_at": 0}, {"channel": "dev"}, {"digest": "bad"}, {"updated_at": time.time() + 1000}])
def test_stale_or_mismatched_status_blocks_update(tmp_path, changes):
    status(tmp_path, **changes)
    with pytest.raises(SelfUpdateError) as error:
        image_update.read_status(tmp_path)
    assert error.value.code == "image_updater_unavailable"


def test_changed_registry_target_and_recovery_marker_block_queue(tmp_path, monkeypatch):
    status(tmp_path)
    monkeypatch.setattr(image_update, "fetch_digest", lambda _: OLD)
    with pytest.raises(SelfUpdateError, match="渠道已变化"):
        image_update.request_image_update(tmp_path, NEW)
    image_update.write_json(tmp_path / "image-recovery.json", {})
    assert image_update.update_blocker(tmp_path) == "image_recovery_required"
    assert not (tmp_path / "image-pending.json").exists()


def test_registry_digest_is_verified_and_credentials_are_not_reported(monkeypatch):
    body = b'{"schemaVersion":2}'
    digest = "sha256:" + hashlib.sha256(body).hexdigest()
    token = Mock()
    token.__enter__ = Mock(return_value=token)
    token.__exit__ = Mock(return_value=False)
    token.read.return_value = '{"token":"private-token"}'
    manifest = Mock()
    manifest.__enter__ = Mock(return_value=manifest)
    manifest.__exit__ = Mock(return_value=False)
    manifest.headers = {"Docker-Content-Digest": digest}
    manifest.read.return_value = body
    network = Mock(side_effect=[token, manifest])
    monkeypatch.setattr(image_update, "urlopen", network)
    assert image_update.fetch_digest("latest") == digest
    assert network.call_args.args[0].full_url == "https://ghcr.io/v2/ariember/maibot/manifests/latest"
    manifest.headers["Docker-Content-Digest"] = NEW
    network.side_effect = [token, manifest]
    with pytest.raises(SelfUpdateError) as error:
        image_update.fetch_digest("latest")
    assert "private-token" not in str(error.value)


def test_image_and_removed_package_deployments(tmp_path, monkeypatch):
    monkeypatch.setenv("MAIBOT_CONTAINER_IMAGE", "1")
    state = tmp_path / "data" / "self_update"
    status(state)
    monkeypatch.setattr(image_update, "fetch_digest", lambda _: NEW)
    local = self_update.inspect_local(tmp_path)
    assert (local.deployment_type, local.commit) == ("image", OLD)
    assert self_update.check_for_update(tmp_path, source_id="ghcr").can_apply
    request = self_update.request_update(NEW, tmp_path, source_id="ghcr")
    assert request.source_id == "ghcr"
    assert not self_update.check_for_update(tmp_path, source_id="ghcr").can_apply
    assert self_update.apply_pending_update(Mock(), tmp_path) is None
    monkeypatch.delenv("MAIBOT_CONTAINER_IMAGE")
    monkeypatch.setattr(self_update, "PACKAGED_INSTALL", True)
    assert self_update.inspect_local(tmp_path).blocker == "package_update_removed"
    with pytest.raises(SelfUpdateError, match="Python 包自更新已移除"):
        self_update.request_update("1.3.20", tmp_path)


def test_git_updates_use_fork_and_reject_upstream_mirror():
    assert self_update.select_update_source("github").url == "https://github.com/Ariember/MaiBot.git"
    with pytest.raises(SelfUpdateError):
        self_update.select_update_source("cnb")


def test_instance_lock_releases_after_close(tmp_path):
    path = tmp_path / "lock"
    with FileLock(path), pytest.raises(OSError):
        FileLock(path)
    with FileLock(path):
        pass


def make_updater(tmp_path, monkeypatch):
    updater = image_updater.ImageUpdater(tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "database").write_text("original")
    container = {
        "Config": {"Labels": {"org.opencontainers.image.version": "1.0"}},
        "State": {"Running": False},
        "Mounts": [{"Type": "bind", "Source": str(tmp_path / "data"), "Destination": "/MaiMBot/data"}],
    }
    monkeypatch.setattr(updater, "inspect", lambda: container)
    monkeypatch.setattr(updater, "current_digest", lambda _: OLD)
    monkeypatch.setattr(updater, "compose", Mock())
    monkeypatch.setattr(image_updater, "fetch_digest", lambda _: NEW)
    monkeypatch.setattr(image_updater, "run", Mock(return_value=json.dumps([{
        "Config": {"Healthcheck": {"Test": ["CMD", "health"]}, "Labels": {"org.opencontainers.image.version": "2.0"}},
    }])))
    pending = {"base_commit": OLD, "target_commit": NEW, "branch": "latest", "source_id": "ghcr", "requested_at": time.time()}
    return updater, pending


def test_update_backs_up_before_replacement_and_waits_for_health(tmp_path, monkeypatch):
    updater, pending = make_updater(tmp_path, monkeypatch)
    seen = []

    def start():
        backup = next((tmp_path / "docker-backups").iterdir())
        assert (backup / "files" / "data" / "database").read_text() == "original"
        assert NEW in updater.override.read_text()
        seen.append("healthy")
        monkeypatch.setattr(updater, "current_digest", lambda _: NEW)

    monkeypatch.setattr(updater, "start_core", start)
    result = updater.execute(pending)
    assert result.success and result.stage == "done" and seen == ["healthy"]
    assert result.backup_path
    assert not (updater.state / "image-recovery.json").exists()


@pytest.mark.parametrize("phase", ["pull", "backup", "health"])
def test_failure_preserves_data_and_never_opens_migrated_data_with_old_image(tmp_path, monkeypatch, phase):
    updater, pending = make_updater(tmp_path, monkeypatch)
    start = Mock()
    monkeypatch.setattr(updater, "start_core", start)
    if phase == "pull":
        monkeypatch.setattr(image_updater, "run", Mock(side_effect=RuntimeError("offline")))
    elif phase == "backup":
        monkeypatch.setattr(updater, "save_backup", Mock(side_effect=OSError("disk full")))
    else:
        start.side_effect = RuntimeError("unhealthy")
    result = updater.execute(pending)
    assert not result.success
    assert (tmp_path / "data" / "database").read_text() == "original"
    if phase == "pull":
        updater.compose.assert_not_called()
    elif phase == "backup":
        assert result.rolled_back and start.call_count == 1
    else:
        assert not result.rolled_back and start.call_count == 1
        assert (updater.state / "image-recovery.json").exists()
        assert NEW in updater.override.read_text()


@pytest.mark.parametrize("mutation", [{"base_commit": NEW}, {"branch": "dev"}, {"requested_at": 0}, {"target_commit": "evil"}])
def test_executor_revalidates_before_stopping(tmp_path, monkeypatch, mutation):
    updater, pending = make_updater(tmp_path, monkeypatch)
    result = updater.execute({**pending, **mutation})
    assert not result.success
    updater.compose.assert_not_called()


def test_custom_override_and_external_mount_are_not_overwritten(tmp_path, monkeypatch):
    updater, pending = make_updater(tmp_path, monkeypatch)
    updater.override.write_text('services:\n  core:\n    ports: ["9000:8001"]')
    original = updater.override.read_bytes()
    assert not updater.execute(pending).success
    assert updater.override.read_bytes() == original
    with pytest.raises(ValueError, match="持久数据必须"):
        updater.data_paths({"Mounts": [{"Type": "bind", "Source": str(tmp_path.parent), "Destination": "/MaiMBot/data"}]})


def test_explicit_restore_preserves_failed_data_and_restores_snapshot(tmp_path, monkeypatch):
    updater, _ = make_updater(tmp_path, monkeypatch)
    backup = tmp_path / "docker-backups" / "snapshot"
    updater.save_backup([tmp_path / "data"], backup, OLD)
    (tmp_path / "data" / "database").write_text("migrated")
    (tmp_path / "data" / "new-file").write_text("new")
    image_update.write_json(updater.state / "image-recovery.json", {})
    monkeypatch.setattr(updater, "start_core", Mock())
    monkeypatch.setattr(updater, "publish_status", Mock())
    updater.restore(backup)
    assert (tmp_path / "data" / "database").read_text() == "original"
    assert not (tmp_path / "data" / "new-file").exists()
    preserved = next(backup.glob("after-failure-*"))
    assert (preserved / "data" / "database").read_text() == "migrated"
    assert (preserved / "data" / "new-file").read_text() == "new"
    assert OLD in updater.override.read_text()
    assert not (updater.state / "image-recovery.json").exists()


def test_restore_rejects_paths_outside_backup_before_stopping(tmp_path, monkeypatch):
    updater, _ = make_updater(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="只能恢复"):
        updater.restore(tmp_path.parent)
    backup = tmp_path / "docker-backups" / "bad"
    image_update.write_json(backup / "manifest.json", {"digest": OLD, "paths": ["../outside"]})
    with pytest.raises(ValueError, match="备份路径"):
        updater.restore(backup)
    updater.compose.assert_not_called()


def test_inspection_validates_compose_owner_and_repository(tmp_path, monkeypatch):
    updater = image_updater.ImageUpdater(tmp_path)
    labels = {
        "com.docker.compose.service": "core", "com.docker.compose.project": "maibot",
        "com.docker.compose.project.working_dir": str(tmp_path),
        "com.docker.compose.project.config_files": str(tmp_path / "docker-compose.yml"),
    }
    container = {"Config": {"Labels": labels, "Image": image_update.IMAGE_REPOSITORY + "@" + OLD}, "Image": "local-image-id"}

    def command(args, **kwargs):
        if args[1] == "inspect":
            return json.dumps([container])
        return json.dumps([{"RepoDigests": [image_update.IMAGE_REPOSITORY + "@" + NEW, image_update.IMAGE_REPOSITORY + "@" + OLD]}])

    monkeypatch.setattr(image_updater, "run", command)
    updater.publish_status()
    assert image_update.read_status(updater.state)["digest"] == OLD
    assert updater.project == "maibot"
    labels["com.docker.compose.service"] = "napcat"
    with pytest.raises(ValueError, match="不是 Compose core"):
        updater.inspect()
    labels["com.docker.compose.service"] = "core"
    labels["com.docker.compose.project.working_dir"] = str(tmp_path.parent)
    with pytest.raises(ValueError, match="工作目录"):
        updater.inspect()
    labels["com.docker.compose.project.working_dir"] = str(tmp_path)
    labels["com.docker.compose.project.config_files"] += ",extra.yml"
    with pytest.raises(ValueError, match="额外"):
        updater.inspect()


def test_service_consumes_request_once_and_blocks_interrupted_task(tmp_path, monkeypatch):
    class StopService(BaseException):
        pass

    updater = image_updater.ImageUpdater(tmp_path)
    monkeypatch.setattr(updater, "publish_status", lambda: None)
    execute = Mock()
    monkeypatch.setattr(updater, "execute", execute)
    monkeypatch.setattr(image_updater.time, "sleep", Mock(side_effect=StopService))
    image_update.write_json(updater.state / "image-pending.json", {"target_commit": NEW})
    with pytest.raises(StopService):
        updater.serve()
    execute.assert_called_once_with({"target_commit": NEW})
    assert not (updater.state / "image-active.json").exists()
    image_update.write_json(updater.state / "image-active.json", {"target_commit": NEW})
    with pytest.raises(StopService):
        updater.serve()
    assert (updater.state / "image-recovery.json").exists()
    assert execute.call_count == 1


def test_data_paths_deduplicate_nested_mounts_and_skip_state(tmp_path):
    updater = image_updater.ImageUpdater(tmp_path)
    (tmp_path / "data" / "plugins").mkdir(parents=True)
    mounts = [
        {"Type": "bind", "Source": str(tmp_path / "data"), "Destination": "/MaiMBot/data"},
        {"Type": "bind", "Source": str(tmp_path / "data" / "plugins"), "Destination": "/MaiMBot/plugins"},
        {"Type": "bind", "Source": str(updater.state), "Destination": "/MaiMBot/data/self_update"},
    ]
    assert updater.data_paths({"Mounts": mounts}) == [tmp_path / "data"]
    mounts[-1]["Source"] = str(tmp_path / "wrong")
    with pytest.raises(ValueError, match="状态目录"):
        updater.data_paths({"Mounts": mounts})


def test_register_instance_prevents_duplicate_runner(tmp_path, monkeypatch):
    monkeypatch.setattr("src.common.instance_lock.sys.prefix", str(tmp_path / "env"))
    with register_instance(tmp_path), pytest.raises(RuntimeError, match="正在运行"):
        register_instance(tmp_path)


def test_docker_healthcheck_uses_shared_bind_address(monkeypatch):
    response = Mock(status=200)
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = '{"status":"healthy"}'
    request = Mock(return_value=response)
    monkeypatch.setattr(docker_healthcheck, "get_local_http_base_url", lambda: "http://[::1]:9001")
    monkeypatch.setattr(docker_healthcheck, "urlopen", request)
    docker_healthcheck.main()
    request.assert_called_once_with("http://[::1]:9001/api/webui/health", timeout=3)
    response.status = 503
    with pytest.raises(RuntimeError, match="健康检查"):
        docker_healthcheck.main()
