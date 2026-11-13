from types import SimpleNamespace
from unittest.mock import AsyncMock

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from maibot_sdk import Field, MaiBotPlugin, PluginConfigBase
import pytest

from src.plugin_runtime import integration
from src.plugin_runtime.runner import plugin_paths
from src.plugin_runtime.runner.plugin_enabled import is_plugin_disabled
from src.plugin_runtime.runner.runner_main import PluginRunner
from src.webui.routers.plugin import config_routes, management, runtime_routes, support


PLUGIN_ID = "test.builtin-life"


class PluginSection(PluginConfigBase):
    enabled: bool = False
    config_version: str = "1.0.0"


class LifeConfig(PluginConfigBase):
    plugin: PluginSection = Field(default_factory=PluginSection)
    interval: int = 30


class LifePlugin(MaiBotPlugin):
    config_model = LifeConfig


@pytest.fixture
def builtin(tmp_path, monkeypatch):
    package_root = tmp_path / "package" / "src"
    plugin_dir = package_root / "plugins" / "built_in" / "mylife"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "_manifest.json").write_text(json.dumps({
        "id": PLUGIN_ID, "name": "麦日常", "version": "1.0.0", "description": "daily life",
    }), encoding="utf-8")
    (plugin_dir / "plugin.py").write_text("", encoding="utf-8")
    external = tmp_path / "instance" / "plugins"
    external.mkdir(parents=True)
    monkeypatch.setattr(plugin_paths, "PACKAGE_ROOT", package_root)
    monkeypatch.setattr(plugin_paths, "get_instance_root", lambda: tmp_path / "instance")
    monkeypatch.setattr(support, "PACKAGE_ROOT", package_root)
    monkeypatch.setattr(support, "get_plugins_dir", lambda: external)
    return plugin_dir


@pytest.fixture
def client(builtin, monkeypatch):
    runner = PluginRunner(host_address="unused", session_token="test", plugin_dirs=[str(builtin.parent)])
    meta = SimpleNamespace(
        plugin_id=PLUGIN_ID, plugin_dir=str(builtin), instance=LifePlugin(), version="1.0.0",
        manifest=SimpleNamespace(name="麦日常", description="", author=SimpleNamespace(name="test")),
    )
    runner._apply_plugin_config(meta)

    async def inspect(plugin_id, config_data=None, *, use_provided_config=False):
        assert plugin_id == PLUGIN_ID
        return runner._inspect_plugin_config(meta, config_data=config_data, use_provided_config=use_provided_config)

    async def validate(plugin_id, config_data):
        return (await inspect(plugin_id, config_data, use_provided_config=True)).normalized_config

    async def apply(plugin_id, write_config):
        assert plugin_id == PLUGIN_ID
        await write_config()
        return "stopped"

    manager = SimpleNamespace(
        apply_plugin_config=apply,
        get_plugin_state_snapshot=AsyncMock(return_value={
            "statuses": {}, "failure_reasons": {}, "circuit_statuses": {}, "usage_seconds": {}, "running": False,
        }),
    )
    monkeypatch.setattr(integration, "get_plugin_runtime_manager", lambda: manager)
    monkeypatch.setattr(config_routes, "_inspect_plugin_config_via_runtime", inspect)
    monkeypatch.setattr(config_routes, "_validate_plugin_config_via_runtime", validate)
    monkeypatch.setattr(config_routes, "require_plugin_token", lambda _: "ok")
    monkeypatch.setattr(management, "require_plugin_token", lambda _: "ok")
    monkeypatch.setattr(runtime_routes, "require_plugin_token", lambda _: "ok")
    monkeypatch.setattr(runtime_routes.component_query_service, "_iter_supervisors", lambda: [])
    monkeypatch.setattr(management, "update_progress", AsyncMock())
    app = FastAPI()
    app.include_router(config_routes.router, prefix="/plugins")
    app.include_router(management.router, prefix="/plugins")
    app.include_router(runtime_routes.router, prefix="/plugins")
    return TestClient(app)


def test_disabled_builtin_is_configurable_without_exposing_code_management(client, builtin):
    assert client.get("/plugins/installed").json()["plugins"] == []
    plugins = client.get("/plugins/installed?include_builtin=true").json()["plugins"]
    assert [(item["id"], item["builtin"], item["enabled"]) for item in plugins] == [(PLUGIN_ID, True, False)]

    bundle = client.get(f"/plugins/config/{PLUGIN_ID}/bundle")
    assert bundle.status_code == 200
    assert bundle.json()["schema"]["sections"]
    assert bundle.json()["config"]["plugin"]["enabled"] is False
    components = client.get(f"/plugins/runtime/plugins/{PLUGIN_ID}/components")
    assert components.status_code == 200
    assert components.json()["components"] == []
    saved = client.put(f"/plugins/config/{PLUGIN_ID}", json={"config": {"general": {"interval": 45}}})
    assert saved.status_code == 200
    assert PluginRunner._load_plugin_config(str(builtin))["interval"] == 45
    toggled = client.post(f"/plugins/config/{PLUGIN_ID}/toggle")
    assert toggled.status_code == 200
    assert toggled.json()["enabled"] is True
    assert not is_plugin_disabled(builtin)
    assert not (builtin / "config.toml").exists()

    for operation in ("uninstall", "update"):
        response = client.post(f"/plugins/{operation}", json={"plugin_id": PLUGIN_ID})
        assert response.status_code == 404
    assert (builtin / "plugin.py").is_file()


def test_builtin_config_moves_to_instance_once_and_reset_does_not_restore_old_values(builtin):
    original = builtin / "config.toml"
    original.write_text('[plugin]\nenabled = false\nconfig_version = "1.0.0"\n', encoding="utf-8")
    config_path = plugin_paths.get_plugin_config_path(builtin)
    assert config_path == plugin_paths.get_instance_root() / "data" / "plugins" / PLUGIN_ID / "config.toml"
    assert PluginRunner._load_plugin_config(str(builtin))["plugin"]["enabled"] is False
    assert is_plugin_disabled(builtin)
    assert not original.exists()
    config_path.unlink()
    assert not plugin_paths.get_plugin_config_path(builtin).exists()


@pytest.mark.asyncio
async def test_builtin_config_directory_is_watched_without_watching_it_as_source(builtin, monkeypatch):
    captured = {}

    class Watcher:
        def __init__(self, *, paths, **kwargs):
            captured["paths"] = paths

        def subscribe(self, callback, *, paths):
            captured["source_paths"] = paths
            return "source"

        async def start(self):
            pass

    manager = integration.PluginRuntimeManager()
    monkeypatch.setattr(manager, "_iter_plugin_dirs", lambda: iter([builtin.parent]))
    monkeypatch.setattr(manager, "_iter_watchable_plugin_paths", lambda: iter([(PLUGIN_ID, builtin)]))
    monkeypatch.setattr(manager, "_refresh_plugin_config_watch_subscriptions", AsyncMock())
    monkeypatch.setattr(integration, "FileWatcher", Watcher)
    await manager._start_plugin_file_watcher()
    config_path = plugin_paths.get_plugin_config_path(builtin)
    assert config_path.parent in captured["paths"]
    assert captured["source_paths"] == [builtin.parent.resolve()]
    assert manager._resolve_plugin_config_path(PLUGIN_ID, builtin) == config_path
