from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zipfile import ZipFile, ZipInfo

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import json
import stat

import pytest

from src.plugin_runtime.runner.manifest_validator import ManifestValidator
from src.plugin_runtime import integration
from src.webui.routers.plugin import support, zip_install


@pytest.fixture
def runtime(monkeypatch):
    async def run_update(operation):
        await operation()

    manager = SimpleNamespace(run_plugin_file_update=AsyncMock(side_effect=run_update))
    monkeypatch.setattr(integration, "get_plugin_runtime_manager", lambda: manager)
    monkeypatch.setattr(zip_install, "_stop_runtime", AsyncMock(return_value=[]))
    monkeypatch.setattr(zip_install, "_resume_runtime", AsyncMock())
    return manager


@pytest.fixture
def client(tmp_path, monkeypatch, runtime):
    root = tmp_path / "plugins"
    root.mkdir()
    monkeypatch.setattr(support, "get_plugins_dir", lambda: root)
    monkeypatch.setattr(zip_install, "get_plugins_dir", lambda: root)
    monkeypatch.setattr(zip_install, "require_plugin_token", lambda _: "ok")
    monkeypatch.setattr(
        zip_install,
        "ManifestValidator",
        lambda **kwargs: ManifestValidator(
            host_version="1.3.0",
            sdk_version="2.8.1",
            **kwargs,
        ),
    )
    app = FastAPI()
    app.include_router(zip_install.router)
    return TestClient(app), root


def archive(prefix="", manifest_changes=None, extra=None, files=None):
    manifest = {
        "manifest_version": 2,
        "id": "example.demo",
        "version": "1.0.0",
        "name": "ZIP 插件",
        "description": "测试 ZIP 安装",
        "author": {"name": "作者", "url": "https://github.com/example"},
        "license": "MIT",
        "urls": {"repository": "https://github.com/example/demo"},
        "host_application": {"min_version": "1.0.0", "max_version": "9.99.99"},
        "sdk": {"min_version": "2.0.0", "max_version": "2.99.99"},
        "dependencies": [],
        "capabilities": [],
        "i18n": {"default_locale": "zh-CN", "supported_locales": ["zh-CN"]},
    }
    manifest.update(manifest_changes or {})
    buffer = BytesIO()
    with ZipFile(buffer, "w") as output:
        output.writestr(prefix + "_manifest.json", json.dumps(manifest))
        output.writestr(prefix + "plugin.py", "raise RuntimeError('安装时不应执行插件')")
        for name, content in (files or {}).items():
            output.writestr(prefix + name, content)
        if extra is not None:
            if isinstance(extra, str) and "\\" in extra:
                # Windows 的 ZipInfo 构造器会自动替换反斜杠，手动保留以模拟外部 ZIP。
                raw_entry = ZipInfo(extra)
                raw_entry.filename = extra
                extra = raw_entry
            output.writestr(extra, "unsafe")
    return buffer.getvalue()


@pytest.mark.parametrize("prefix", ["", "demo-main/"])
def test_install_valid_archive(client, prefix):
    api, root = client
    data = archive(prefix)
    response = api.post("/install-zip", files={"file": ("plugin.zip", data)})
    assert response.status_code == 200, response.text
    assert (root / "example_demo" / "plugin.py").is_file()
    assert not response.json().get("updated")
    assert sorted(path.name for path in root.iterdir()) == ["example_demo"]


@pytest.mark.parametrize("folder", ["example_demo", "example.demo", "custom-folder"])
@pytest.mark.parametrize("prefix", ["", "demo-main/"])
def test_update_preserves_user_files_and_backs_up_old_version(client, monkeypatch, runtime, folder, prefix):
    api, root = client
    assert api.post("/install-zip", files={"file": ("plugin.zip", archive())}).status_code == 200
    target = root / folder
    if folder != "example_demo":
        (root / "example_demo").rename(target)
    config = "[plugin]\nenabled = false\n"
    (target / "config.toml").write_text(config, encoding="utf-8")
    (target / "config_back").mkdir()
    (target / "config_back" / "saved.toml").write_text(config, encoding="utf-8")
    (target / "data").mkdir()
    (target / "data" / "state.json").write_text("old", encoding="utf-8")
    (target / "obsolete.py").write_text("old code", encoding="utf-8")
    (target / "custom.json").write_text("custom data", encoding="utf-8")
    (target / ".maibot-release.json").write_text("{}", encoding="utf-8")

    async def stop(plugin_id):
        assert plugin_id == "example.demo"
        assert (target / "obsolete.py").exists()
        (target / "data" / "state.json").write_text("flushed on stop", encoding="utf-8")
        return [plugin_id]

    async def resume(plugin_ids):
        assert plugin_ids == ["example.demo"]
        assert json.loads((target / "_manifest.json").read_text(encoding="utf-8"))["version"] == "2.0.0"

    monkeypatch.setattr(zip_install, "_stop_runtime", AsyncMock(side_effect=stop))
    monkeypatch.setattr(zip_install, "_resume_runtime", AsyncMock(side_effect=resume))
    data = archive(prefix, {"version": "2.0.0"}, files={"config.toml": "[plugin]\nenabled = true\n"})
    response = api.post("/install-zip", files={"file": ("plugin.zip", data)})
    assert response.status_code == 200, response.text
    assert response.json()["updated"] is True
    assert "更新成功" in response.json()["message"]
    assert (target / "config.toml").read_text(encoding="utf-8") == config
    assert (target / "config_back" / "saved.toml").read_text(encoding="utf-8") == config
    assert (target / "data" / "state.json").read_text(encoding="utf-8") == "flushed on stop"
    assert not (target / "obsolete.py").exists()
    assert not (target / ".maibot-release.json").exists()
    backup = Path(response.json()["backup_path"])
    assert backup.is_relative_to(root / ".update_backups")
    assert (backup / "obsolete.py").read_text(encoding="utf-8") == "old code"
    assert (backup / "custom.json").read_text(encoding="utf-8") == "custom data"
    assert json.loads((backup / "_manifest.json").read_text(encoding="utf-8"))["version"] == "1.0.0"
    assert sorted(path.name for path in root.iterdir()) == [".update_backups", folder]
    runtime.run_plugin_file_update.assert_awaited_once()
    zip_install._resume_runtime.assert_awaited_once()


@pytest.mark.parametrize("manifest", [None, "invalid JSON", '{"id": "other.plugin"}'])
@pytest.mark.parametrize("folder", ["example_demo", "example.demo"])
def test_install_refuses_unrelated_or_invalid_existing_directory(client, manifest, folder):
    api, root = client
    target = root / folder
    target.mkdir()
    (target / "keep.txt").write_text("keep", encoding="utf-8")
    if manifest is not None:
        (target / "_manifest.json").write_text(manifest, encoding="utf-8")
    response = api.post("/install-zip", files={"file": ("plugin.zip", archive())})
    assert response.status_code == 409
    assert (target / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert sorted(path.name for path in root.iterdir()) == [folder]


def test_update_rolls_back_when_replacement_fails(client, monkeypatch):
    api, root = client
    api.post("/install-zip", files={"file": ("plugin.zip", archive())})
    target = root / "example_demo"
    original = (target / "_manifest.json").read_bytes()
    rename = Path.rename

    def fail_replacement(source, destination):
        if source.name.startswith(".zip-install-") and destination == target:
            raise OSError("replacement failed")
        return rename(source, destination)

    async def resume(plugin_ids):
        assert plugin_ids == ["example.demo"]
        assert (target / "_manifest.json").read_bytes() == original

    monkeypatch.setattr(Path, "rename", fail_replacement)
    monkeypatch.setattr(zip_install, "_stop_runtime", AsyncMock(return_value=["example.demo"]))
    monkeypatch.setattr(zip_install, "_resume_runtime", AsyncMock(side_effect=resume))
    response = api.post("/install-zip", files={"file": ("plugin.zip", archive(manifest_changes={"version": "2.0.0"}))})
    assert response.status_code == 500
    assert "replacement failed" in response.json()["detail"]
    assert (target / "_manifest.json").read_bytes() == original
    assert not list((root / ".update_backups").iterdir())
    assert not list(root.glob(".zip-install-*"))
    zip_install._resume_runtime.assert_awaited_once()


def test_update_rejects_data_collision_and_releases_operation_lock(client):
    api, root = client
    api.post("/install-zip", files={"file": ("plugin.zip", archive())})
    data = root / "example_demo" / "data"
    data.mkdir()
    (data / "keep.txt").write_text("keep", encoding="utf-8")
    response = api.post("/install-zip", files={"file": ("plugin.zip", archive(files={"data/keep.txt": "overwrite"}))})
    assert response.status_code == 409
    assert (data / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert not list((root / ".update_backups").iterdir())
    assert api.post("/install-zip", files={"file": ("plugin.zip", archive())}).status_code == 200


def test_update_stop_failure_leaves_old_version_untouched(client, monkeypatch):
    api, root = client
    api.post("/install-zip", files={"file": ("plugin.zip", archive())})
    target = root / "example_demo"
    original = (target / "_manifest.json").read_bytes()
    monkeypatch.setattr(zip_install, "_stop_runtime", AsyncMock(side_effect=HTTPException(409, "停止插件失败")))
    response = api.post("/install-zip", files={"file": ("plugin.zip", archive(manifest_changes={"version": "2.0.0"}))})
    assert response.status_code == 409
    assert (target / "_manifest.json").read_bytes() == original
    zip_install._resume_runtime.assert_not_awaited()


@pytest.mark.parametrize("copy_fails", [False, True])
def test_update_reports_reload_failure_and_preserves_recoverable_files(client, monkeypatch, copy_fails):
    api, root = client
    api.post("/install-zip", files={"file": ("plugin.zip", archive())})
    target = root / "example_demo"

    def fail_copy(*args):
        raise OSError("copy failed")

    if copy_fails:
        monkeypatch.setattr(zip_install, "_preserve_user_files", fail_copy)
    monkeypatch.setattr(zip_install, "_stop_runtime", AsyncMock(return_value=["example.demo"]))
    monkeypatch.setattr(zip_install, "_resume_runtime", AsyncMock(side_effect=HTTPException(409, "重新加载失败")))
    response = api.post("/install-zip", files={"file": ("plugin.zip", archive(manifest_changes={"version": "2.0.0"}))})
    assert response.status_code == (500 if copy_fails else 409)
    assert "重新加载失败" in response.json()["detail"]
    if copy_fails:
        assert "copy failed" in response.json()["detail"]
    expected_version = "1.0.0" if copy_fails else "2.0.0"
    assert json.loads((target / "_manifest.json").read_text(encoding="utf-8"))["version"] == expected_version
    backups = list((root / ".update_backups").iterdir())
    assert len(backups) == (0 if copy_fails else 1)
    if backups:
        assert json.loads((backups[0] / "_manifest.json").read_text(encoding="utf-8"))["version"] == "1.0.0"
    assert not list(root.glob(".zip-install-*"))


@pytest.mark.parametrize("changes, status", [({"manifest_version": 1}, 400), ({"id": "Example.demo"}, 409)])
def test_invalid_update_leaves_installed_plugin_untouched(client, changes, status):
    api, root = client
    api.post("/install-zip", files={"file": ("plugin.zip", archive())})
    target = root / "example_demo"
    original = (target / "_manifest.json").read_bytes()
    response = api.post("/install-zip", files={"file": ("plugin.zip", archive(manifest_changes=changes))})
    assert response.status_code == status
    assert (target / "_manifest.json").read_bytes() == original
    assert sorted(path.name for path in root.iterdir()) == ["example_demo"]
    zip_install._stop_runtime.assert_not_awaited()


@pytest.mark.parametrize("link_name", [".update_backups", "example_demo/data"])
def test_update_refuses_links_to_external_data(client, tmp_path, link_name):
    api, root = client
    api.post("/install-zip", files={"file": ("plugin.zip", archive())})
    external = tmp_path / "external"
    external.mkdir()
    (external / "keep.txt").write_text("keep", encoding="utf-8")
    link = root / link_name
    try:
        link.symlink_to(external, target_is_directory=True)
    except OSError:
        pytest.skip("当前系统不支持创建符号链接")
    original = (root / "example_demo" / "_manifest.json").read_bytes()
    response = api.post("/install-zip", files={"file": ("plugin.zip", archive(manifest_changes={"version": "2.0.0"}))})
    assert response.status_code == 400
    assert (root / "example_demo" / "_manifest.json").read_bytes() == original
    assert (external / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert sorted(path.name for path in external.iterdir()) == ["keep.txt"]
    zip_install._stop_runtime.assert_not_awaited()


def test_zip_install_rejects_concurrent_update(client):
    api, root = client
    with zip_install._reserve_plugin_operation("example.demo", "update"):
        response = api.post("/install-zip", files={"file": ("plugin.zip", archive())})
    assert response.status_code == 409
    assert list(root.iterdir()) == []


@pytest.mark.parametrize("changes", [{"manifest_version": 1}, {"id": "../escape"}, {"sdk": {"min_version": "99.0.0"}}])
def test_invalid_manifest_leaves_plugins_untouched(client, changes):
    api, root = client
    response = api.post("/install-zip", files={"file": ("plugin.zip", archive(manifest_changes=changes))})
    assert response.status_code == 400
    assert list(root.iterdir()) == []


@pytest.mark.parametrize(
    "extra",
    [
        "../escape",
        "/absolute",
        "C:/escape",
        "demo\\escape",
        "file:stream",
        "CON.txt",
        "_manifest.json",
        ".maibot-release.json",
    ],
)
def test_reject_unsafe_archive_entries(client, extra):
    api, root = client
    response = api.post("/install-zip", files={"file": ("plugin.zip", archive(extra=extra))})
    assert response.status_code == 400
    assert list(root.iterdir()) == []


def test_reject_links_corruption_and_size_limit(client, monkeypatch):
    api, root = client
    link = ZipInfo("link")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    for data in (archive(extra=link), b"not a zip"):
        assert api.post("/install-zip", files={"file": ("plugin.zip", data)}).status_code == 400
    monkeypatch.setattr(zip_install, "MAX_EXTRACTED_BYTES", 1)
    assert api.post("/install-zip", files={"file": ("plugin.zip", archive())}).status_code == 400
    monkeypatch.setattr(zip_install, "MAX_ZIP_BYTES", 1)
    assert api.post("/install-zip", files={"file": ("plugin.zip", archive())}).status_code == 413
    assert list(root.iterdir()) == []


def test_authentication_and_file_extension(client, monkeypatch):
    api, root = client
    assert api.post("/install-zip", files={"file": ("plugin.txt", archive())}).status_code == 400
    monkeypatch.setattr(zip_install, "require_plugin_token", support.require_plugin_token)
    assert api.post("/install-zip", files={"file": ("plugin.zip", archive())}).status_code == 401
    assert list(root.iterdir()) == []


@pytest.mark.parametrize(
    "files",
    [
        {"plugin.py": ""},
        {"_manifest.json": "{}"},
        {"_manifest.json": "invalid JSON", "plugin.py": ""},
        {"a/_manifest.json": "{}", "b/_manifest.json": "{}"},
    ],
)
def test_reject_missing_entrypoint_manifest_or_multiple_plugins(client, files):
    api, root = client
    buffer = BytesIO()
    with ZipFile(buffer, "w") as output:
        for name, content in files.items():
            output.writestr(name, content)
    assert api.post("/install-zip", files={"file": ("plugin.zip", buffer.getvalue())}).status_code == 400
    assert list(root.iterdir()) == []


@pytest.mark.parametrize("sdk", [
    {"min_version": "9.0.0", "max_version": "9.99.99"},
    {"min_version": "1.0.0", "max_version": "1.99.99"},
])
def test_offline_install_allows_sdk_range_mismatch(client, sdk):
    api, root = client
    response = api.post("/install-zip", files={"file": ("plugin.zip", archive(manifest_changes={"sdk": sdk}))})
    assert response.status_code == 200, response.text
    assert json.loads((root / "example_demo" / "_manifest.json").read_text(encoding="utf-8"))["sdk"] == sdk
