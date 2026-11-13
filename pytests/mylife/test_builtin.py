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
    assert "context" not in model_schema["properties"]
    assert "context" not in template
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


@pytest.fixture
def configured_plugin(monkeypatch):
    plugin = plugin_module.MaiLifePlugin()
    plugin.set_plugin_config(MaiLifeSettings(
        plugin={"enabled": True}, users={"owner_only_terms": ["专属称呼"]}
    ).model_dump())
    plugin._env = SimpleNamespace(now=lambda: NOW)
    plugin._store = SimpleNamespace(
        get_state=AsyncMock(return_value={}),
        get_weather=AsyncMock(return_value={"description": "晴天"}),
        proactive_for_task=AsyncMock(return_value={}),
        reserve_reply_turn=AsyncMock(return_value=True),
        save_state=AsyncMock(),
    )
    plugin._schedule = SimpleNamespace(
        context=AsyncMock(return_value={}), ensure_day=AsyncMock(), record_activity=AsyncMock()
    )
    plugin._memory = SimpleNamespace(context_for_user=AsyncMock(return_value={}))
    plugin._information = SimpleNamespace(
        context=AsyncMock(return_value={}), tick=AsyncMock(return_value={})
    )
    plugin._user_by_session = AsyncMock(return_value={"user_id": "10001", "role": "friend"})
    plugin._relay_for_session = AsyncMock(return_value={})
    plugin._activate_planner_task = AsyncMock(return_value=None)
    monkeypatch.setattr(type(plugin), "_ready", property(lambda self: True))
    monkeypatch.setattr(plugin, "_get_logger", Mock(return_value=Mock()))
    return plugin


@pytest.mark.asyncio
async def test_life_background_is_shared_without_a_separate_context_switch(configured_plugin):
    plugin = configured_plugin
    plugin._env.snapshot = Mock(return_value={})
    planner = await plugin.on_planner(session_id="private", messages=[])
    replyer = await plugin.on_replyer(session_id="private", reply_message_id="message")
    planner_prompt = planner["modified_kwargs"]["messages"][0]["content"]
    replyer_prompt = replyer["modified_kwargs"]["extra_prompt"]
    for prompt in (planner_prompt, replyer_prompt):
        assert "晴天" in prompt
        assert "该用户是普通朋友" in prompt
        assert "未完话题" not in prompt
    plugin._memory.context_for_user.assert_awaited_once()
    plugin._information.context.assert_awaited_once()
    assert plugin._store.get_state.await_count == 2

    plugin._group_turns[("group", "group-message")] = {"turn_scope": "group:100"}
    group = await plugin.on_replyer(session_id="group", reply_message_id="group-message")
    assert "该用户是普通朋友" not in group["modified_kwargs"]["extra_prompt"]
    assert plugin._store.get_state.await_count == 2


@pytest.mark.asyncio
async def test_private_supplements_pass_but_group_turns_and_friend_terms_are_checked(configured_plugin):
    plugin = configured_plugin
    for response in ("回答正文", "补充说明"):
        result = await plugin.on_replyer_after(
            session_id="private", reply_message_id="message", response=response
        )
        assert result["modified_kwargs"]["response"] == response
    plugin._store.reserve_reply_turn.assert_not_awaited()

    retry = await plugin.on_replyer_after(
        session_id="private", reply_message_id="message", response="专属称呼", max_retries=1
    )
    assert retry["modified_kwargs"]["retry"] is True
    exhausted = await plugin.on_replyer_after(
        session_id="private", reply_message_id="message", response="专属称呼", retry_count=1, max_retries=1
    )
    assert exhausted["modified_kwargs"]["response"] == ""

    plugin._group_turns[("group", "group-message")] = {"turn_scope": "group:100"}
    plugin._store.reserve_reply_turn.side_effect = [True, False]
    await plugin.on_replyer_after(session_id="group", reply_message_id="group-message", response="群聊回复")
    duplicate = await plugin.on_replyer_after(
        session_id="group", reply_message_id="group-message", response="重复回复"
    )
    assert duplicate["modified_kwargs"]["mai_life_suppress_reason"] == "duplicate_turn"


@pytest.mark.asyncio
async def test_proactive_task_keeps_one_reply_and_its_confirmation_window(configured_plugin):
    plugin = configured_plugin
    task_id = plugin_module.HOST_TASK_PREFIX + "task"
    active = SimpleNamespace(task_id=task_id, record_id="event", sent=False)
    plugin._active_tasks.current = AsyncMock(return_value=active)
    plugin._active_tasks.reserve_reply = AsyncMock(return_value=True)
    plugin._store.proactive_for_task.return_value = {
        "id": "event", "status": "pending", "expires_at": NOW.timestamp() + 120,
    }
    plugin.config.proactive.pending_expire_seconds = 180
    await plugin.on_replyer_after(session_id="private", reply_message_id="message", response="主动分享")
    plugin._store.reserve_reply_turn.assert_awaited_once_with(
        "private", task_id, NOW.timestamp(), NOW.timestamp() + 180
    )
    plugin._active_tasks.reserve_reply.assert_awaited_once_with("private", task_id, "message", NOW.timestamp())

    active.sent = True
    repeated = await plugin.on_replyer_after(
        session_id="private", reply_message_id="message", response="重复分享"
    )
    assert repeated["modified_kwargs"]["mai_life_suppress_reason"] == "active_task_already_sent"


@pytest.mark.asyncio
async def test_exploration_uses_owner_messages_without_separate_topic_analysis(configured_plugin):
    plugin = configured_plugin
    plugin._store.list_users = AsyncMock(return_value=[
        {"user_id": "10001", "role": "owner"}, {"user_id": "10002", "role": "friend"}
    ])
    plugin._store.recent_interactions = AsyncMock(return_value=["天文观测", "普通主题" * 100])
    plugin.config.network.enabled = True
    plugin.config.network.search_include_chat_topics = True
    await plugin._activity_tick()
    plugin._store.recent_interactions.assert_awaited_once_with("10001", 5)
    assert plugin._information.tick.await_args.args[-1] == ["天文观测", ("普通主题" * 100)[:120]]
