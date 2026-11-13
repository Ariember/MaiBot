"""内置模块的配置、日期提醒、存储与页面契约。"""

from datetime import datetime, timezone
from pathlib import Path
from threading import Event, get_ident
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import asyncio
import json
import pytest
import re
import tomllib

from src.plugins.built_in.mylife import plugin as plugin_module
from src.plugins.built_in.mylife.config import CONFIG_SCHEMA_VERSION, MaiLifeSettings, PLUGIN_VERSION
from src.plugins.built_in.mylife.core.storage import LifeStore
from src.plugins.built_in.mylife.life.memory_service import MemoryService


ROOT = Path(plugin_module.__file__).parent
NOW = datetime(2026, 11, 13, 1, tzinfo=timezone.utc)


def test_defaults_template_and_webui_contract():
    plugin = plugin_module.MaiLifePlugin()
    plugin.set_plugin_config({})
    assert plugin.config.plugin.enabled is False
    template = tomllib.loads((ROOT / "config.toml.example").read_text(encoding="utf-8"))
    assert MaiLifeSettings.model_validate(template).plugin.enabled is False
    assert template["plugin"]["config_version"] == CONFIG_SCHEMA_VERSION
    manifest = json.loads((ROOT / "_manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == PLUGIN_VERSION
    assert manifest["id"] == "fraternity-z.mai-mylife"
    model_schema = MaiLifeSettings.model_json_schema()
    assert model_schema["$defs"]["PluginSettings"]["properties"]["enabled"]["hidden"] is True
    assert "reading" not in model_schema["properties"]
    assert "reading" not in template
    schema = json.dumps(model_schema, ensure_ascii=False).lower()
    assert "diary" not in schema
    assert "日记" not in schema
    assert not hasattr(plugin, "webui_memories")

    webui = json.loads((ROOT / "webui.json").read_text(encoding="utf-8"))
    api_names = {item["name"] for item in plugin.get_components() if item["type"] == "API"}
    assert {page["id"] for page in webui["pages"]} == {"overview", "life", "system"}
    for page in webui["pages"]:
        assert page["placement"] == "sidebar"
        for query in (*page.get("queries", {}).values(), *page.get("actions", {}).values()):
            assert query["api"] in api_names
        html = (ROOT / page["entry"]).read_text(encoding="utf-8")
        assert not re.search("diar|日记|手账", html, re.IGNORECASE)
        ids = set(re.findall(r'\bid="([^"]+)"', html))
        bound_ids = set(re.findall(r"document\.getElementById\(['\"]([^'\"]+)['\"]\)", html))
        assert bound_ids <= ids, bound_ids - ids


@pytest.mark.asyncio
async def test_important_dates_still_remind_before_two_am(tmp_path):
    store = LifeStore(str(tmp_path), clock=lambda: NOW.timestamp())
    await store.initialize()
    config = MaiLifeSettings(users={"profiles": [{"user_id": "10001", "role": "owner"}, {"user_id": "10002"}]})
    llm = SimpleNamespace(task_available=Mock(return_value=False), generate_json=AsyncMock())
    memory = MemoryService(store, config, llm, Mock())
    try:
        await store.sync_users(config.users.profiles)
        await memory.observe_message("10001", "11月13日是我的生日", NOW)
        await store.add_important_date("10002", "朋友考试", "2026-11-14", "none", "manual", NOW.timestamp())
        await memory.ensure_daily(NOW)
        await memory.ensure_daily(NOW)
        opportunities = await store.active_opportunities(NOW.timestamp())
        assert len([item for item in opportunities if item["target_user_id"] == "10001"]) == 1
        context = await memory.context_for_user({"user_id": "10001", "role": "owner"}, NOW)
        assert set(context) == {"upcoming_dates"}
        assert [item["name"] for item in context["upcoming_dates"]] == ["生日"]
        assert "朋友考试" not in json.dumps(context, ensure_ascii=False)
        tables = {row[0] for row in store.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "diary_entries" not in tables
        assert not hasattr(store, "save_diary")
        llm.generate_json.assert_not_awaited()
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_database_operations_leave_loop_free_and_finish_before_cancel(tmp_path, monkeypatch):
    store = LifeStore(str(tmp_path))
    started, release = Event(), Event()
    loop_thread = get_ident()
    original = store._create_schema

    def slow_schema():
        assert get_ident() != loop_thread
        started.set()
        assert release.wait(2)
        original()

    monkeypatch.setattr(store, "_create_schema", slow_schema)
    task = asyncio.create_task(store.initialize())
    try:
        assert await asyncio.to_thread(started.wait, 2)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        await store.close()
