"""内置适配器接续保留配置、禁言状态和外置源码备份。"""

from pathlib import Path
from unittest.mock import Mock

import json
import pytest

from src.plugin_runtime import snowluma_migration
from src.plugin_runtime.runner import plugin_paths
from src.plugin_runtime.runner.manifest_validator import is_reserved_plugin_directory
from src.plugins.built_in.snowluma_adapter.services.ban_state_store import QQBanRecord, QQBanStateStore


PLUGIN_ID = snowluma_migration.PLUGIN_ID


def _write_plugin(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "plugin.py").write_text("def create_plugin(): pass\n", encoding="utf-8")
    (path / "_manifest.json").write_text(json.dumps({"id": PLUGIN_ID}), encoding="utf-8")
    return path


@pytest.fixture
def layout(tmp_path, monkeypatch):
    package_root = tmp_path / "package" / "src"
    builtin = _write_plugin(package_root / "plugins" / "built_in" / "snowluma_adapter")
    instance = tmp_path / "instance"
    external = _write_plugin(instance / "plugins" / "snowluma")
    config = b'# connection settings\r\n[plugin]\r\nenabled = false\r\n[connection]\r\nport = 8123\r\n'
    (external / "config.toml").write_bytes(config)
    state = external.parent / "data" / "napcat_adapter" / "ban_state.json"
    state.parent.mkdir(parents=True)
    state.write_bytes(b'[{"group_id":"123","user_id":"456","lift_time":2000000000}]\n')
    monkeypatch.setattr(plugin_paths, "PACKAGE_ROOT", package_root)
    monkeypatch.setattr(plugin_paths, "get_instance_root", lambda: instance)
    return builtin, external, state, instance / "data" / "plugins" / PLUGIN_ID


@pytest.mark.asyncio
async def test_migration_preserves_config_state_and_source_backup(layout):
    builtin, external, state, target = layout
    original_config = (external / "config.toml").read_bytes()
    original_source = (external / "plugin.py").read_bytes()
    roots = [builtin.parent, external.parent]

    snowluma_migration.migrate_snowluma_adapter(roots)

    backup = external.parent / ".builtin-backups" / external.name
    assert (target / "config.toml").read_bytes() == original_config
    assert (target / "ban_state.json").read_bytes() == state.read_bytes()
    store = QQBanStateStore(Mock(), target / "ban_state.json")
    await store.load()
    assert await store.snapshot() == [QQBanRecord(group_id="123", user_id="456", lift_time=2000000000)]
    assert (backup / "plugin.py").read_bytes() == original_source
    assert (backup / "config.toml").read_bytes() == original_config
    assert is_reserved_plugin_directory(backup.parent)
    assert not external.exists()
    assert not (builtin / "config.toml").exists()
    assert not (builtin / "ban_state.json").exists()

    (target / "config.toml").write_bytes(b"[plugin]\nenabled = true\n")
    (target / "ban_state.json").unlink()
    snowluma_migration.migrate_snowluma_adapter(roots + roots)
    assert (target / "config.toml").read_bytes() == b"[plugin]\nenabled = true\n"
    assert not (target / "ban_state.json").exists()
    assert list(backup.parent.iterdir()) == [backup]


def test_existing_instance_files_win_and_previous_backup_is_preserved(layout):
    builtin, external, _, target = layout
    target.mkdir(parents=True)
    (target / "config.toml").write_bytes(b"[plugin]\nenabled = true\n")
    (target / "ban_state.json").write_bytes(b"[]")
    previous = external.parent / ".builtin-backups" / external.name
    previous.mkdir(parents=True)
    (previous / "marker").write_text("keep", encoding="utf-8")

    snowluma_migration.migrate_snowluma_adapter([builtin.parent, external.parent])

    assert (target / "config.toml").read_bytes() == b"[plugin]\nenabled = true\n"
    assert (target / "ban_state.json").read_bytes() == b"[]"
    assert (previous / "marker").read_text(encoding="utf-8") == "keep"
    assert (previous.with_name(previous.name + ".1") / "plugin.py").exists()


def test_multiple_external_copies_remain_for_duplicate_isolation(layout):
    builtin, external, _, target = layout
    second = _write_plugin(external.parent / "second_copy")

    snowluma_migration.migrate_snowluma_adapter([builtin.parent, external.parent])

    assert external.is_dir()
    assert second.is_dir()
    assert not target.exists()


@pytest.mark.parametrize("failure", ["copy", "rename"])
def test_failed_migration_keeps_original_files_and_can_retry(layout, monkeypatch, failure):
    builtin, external, state, target = layout
    original_config = (external / "config.toml").read_bytes()
    original_state = state.read_bytes()
    original_copy = snowluma_migration.shutil.copy2
    original_rename = Path.rename

    def fail_copy(source, destination):
        Path(destination).write_bytes(b"partial")
        raise OSError("disk write failed")

    def fail_rename(source, destination):
        raise OSError("directory is in use")

    if failure == "copy":
        monkeypatch.setattr(snowluma_migration.shutil, "copy2", fail_copy)
    else:
        monkeypatch.setattr(Path, "rename", fail_rename)
    snowluma_migration.migrate_snowluma_adapter([builtin.parent, external.parent])

    assert (external / "config.toml").read_bytes() == original_config
    assert (external / "plugin.py").is_file()
    assert state.read_bytes() == original_state
    assert not (target / ".config.toml.tmp").exists()
    if failure == "copy":
        assert not (target / "config.toml").exists()

    monkeypatch.setattr(snowluma_migration.shutil, "copy2", original_copy)
    monkeypatch.setattr(Path, "rename", original_rename)
    snowluma_migration.migrate_snowluma_adapter([builtin.parent, external.parent])
    assert not external.exists()
    assert (target / "config.toml").read_bytes() == original_config
    assert (target / "ban_state.json").read_bytes() == original_state


def test_no_builtin_does_not_change_external_installation(layout):
    _, external, _, target = layout
    snowluma_migration.migrate_snowluma_adapter([external.parent])
    assert external.is_dir()
    assert not target.exists()
