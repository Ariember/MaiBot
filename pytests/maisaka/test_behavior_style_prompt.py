from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.chat.replyer.maisaka_generator_base import BaseMaisakaReplyGenerator, MaisakaReplyContext
from src.common.data_models.llm_service_data_models import LLMResponseResult
from src.common.i18n import use_locale
from src.common.prompt_i18n import load_prompt
from src.config.config import global_config
from src.llm_models.payload_content.context_item import CONTEXT_ITEM_SCHEMA_VERSION, ContextItemBuilder, RoleType, get_item_text
from src.maisaka.builtin_tool import reply
from src.maisaka.chat_loop_service import MaisakaChatLoopService
from src.plugin_runtime.prompt_sources import collect_prompt_changes


@pytest.mark.parametrize(
    ("locale", "short_marker", "normal_marker", "long_marker"),
    [
        ("zh-CN", "一到两句", "简洁", "关键细节"),
        ("en-US", "one or two short sentences", "concise", "key details"),
        ("ja-JP", "一文か二文", "簡潔", "掘り下げ"),
    ],
)
def test_reply_length_instructions_follow_locale(locale, short_marker, normal_marker, long_marker) -> None:
    build_style = BaseMaisakaReplyGenerator._build_requested_reply_style_message
    with use_locale(locale):
        assert short_marker in build_style("简短表达")
        assert normal_marker in build_style("正常回复")
        assert long_marker in build_style("长回复")
        assert build_style("") == build_style("正常回复")
        assert build_style("未声明的篇幅") == build_style("正常回复")


def test_planner_context_includes_personality_and_behavior_style(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(global_config.personality, "personality", "测试核心人格。")
    monkeypatch.setattr(global_config.personality, "behavior_style", "这段行为风格只应提供给 Planner。")

    service = MaisakaChatLoopService()
    prompt_context = service.build_prompt_template_context()

    assert prompt_context["behavior_style"] == "这段行为风格只应提供给 Planner。"
    assert "identity" not in prompt_context
    assert prompt_context["personality"] == "测试核心人格。"


def test_replyer_keeps_using_personality(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(global_config.personality, "personality", "测试核心人格。")
    monkeypatch.setattr(global_config.personality, "behavior_style", "这段行为风格只应提供给 Planner。")

    generator = object.__new__(BaseMaisakaReplyGenerator)
    prompt = generator._build_personality_prompt()

    assert "测试核心人格。" in prompt
    assert "这段行为风格只应提供给 Planner。" not in prompt


@pytest.mark.parametrize("is_group_chat", [True, False])
@pytest.mark.parametrize("prompt_name", ["maisaka_chat", "maisaka_chat_focus", "maisaka_replyer"])
@pytest.mark.parametrize(
    ("locale", "heading"),
    [("zh-CN", "注意力漂移风格："), ("en-US", "Attention drift style:"), ("ja-JP", "注意ドリフトスタイル：")],
)
def test_attention_drift_follows_live_config_in_planner_and_replyer(
    monkeypatch: pytest.MonkeyPatch, prompt_name: str, locale: str, heading: str, is_group_chat: bool
) -> None:
    if prompt_name == "maisaka_replyer":
        generator = object.__new__(BaseMaisakaReplyGenerator)
        generator._load_prompt = load_prompt
        monkeypatch.setattr(
            "src.chat.replyer.maisaka_generator_base.get_chat_type_and_target_info",
            lambda session_id: (is_group_chat, None),
        )
        monkeypatch.setattr(generator, "_build_group_chat_attention_block", lambda session_id: "")
        monkeypatch.setattr(generator, "_build_personality_prompt", lambda prompt_sources=None: "测试人设")
        monkeypatch.setattr(generator, "_select_reply_style", lambda: "测试回复风格")

        def build_prompt() -> str:
            return generator._build_system_prompt(None, "测试回复原因", stream_id="test-session")
    else:
        service = MaisakaChatLoopService(is_group_chat=is_group_chat)
        monkeypatch.setattr(service, "_get_chat_prompt_name", lambda: prompt_name)
        build_prompt = service._build_chat_system_prompt

    config = (
        global_config.experimental.group_attention_drift
        if is_group_chat
        else global_config.experimental.private_attention_drift
    )
    other_config = (
        global_config.experimental.private_attention_drift
        if is_group_chat
        else global_config.experimental.group_attention_drift
    )
    monkeypatch.setattr(other_config, "enabled", True)
    with use_locale(locale):
        monkeypatch.setattr(config, "enabled", False)
        baseline = build_prompt()
        if prompt_name == "maisaka_replyer":
            assert "测试人设" in baseline
        assert heading not in baseline
        monkeypatch.setattr(config, "enabled", True)
        assert build_prompt().count(heading) == 1
        monkeypatch.setattr(config, "enabled", False)
        assert build_prompt() == baseline


@pytest.mark.parametrize("prompt_name", ["maisaka_chat", "maisaka_chat_focus"])
@pytest.mark.parametrize("locale", ["zh-CN", "en-US", "ja-JP"])
def test_planner_personality_precedes_behavior_style(
    monkeypatch: pytest.MonkeyPatch, prompt_name: str, locale: str
) -> None:
    monkeypatch.setattr(global_config.personality, "personality", "核心人格测试标记")
    monkeypatch.setattr(global_config.personality, "behavior_style", "行为风格测试标记")
    service = MaisakaChatLoopService()
    monkeypatch.setattr(service, "_get_chat_prompt_name", lambda: prompt_name)

    with use_locale(locale):
        prompt = service._build_chat_system_prompt()

    assert prompt.index("核心人格测试标记") < prompt.index("行为风格测试标记")


def test_reply_tool_offers_configured_persona_styles_only_when_enabled(monkeypatch):
    monkeypatch.setattr(reply, "build_reply_extensions_schema", lambda context: None)
    monkeypatch.setattr(global_config.personality, "multiple_reply_style", [" 轻松 ", "", "认真", "轻松"])
    monkeypatch.setattr(global_config.personality, "multiple_probability", 0.5)
    schema = reply.get_tool_spec().parameters_schema
    assert schema["properties"]["persona_style"]["enum"] == ["轻松", "认真"]
    assert "persona_style" not in schema["required"]
    monkeypatch.setattr(global_config.personality, "multiple_probability", 0)
    assert "persona_style" not in reply.get_tool_spec().parameters_schema["properties"]


@pytest.mark.parametrize("locale,group_marker", [("en-US", "QQ group"), ("ja-JP", "QQ グループ")])
def test_replyer_template_does_not_assume_group_chat(locale, group_marker):
    with use_locale(locale):
        prompt = load_prompt(
            "maisaka_replyer", identity="PERSONA", reply_style="STYLE", group_chat_attention_block="PRIVATE",
            replyer_output_instruction="OUTPUT",
        )
    assert group_marker not in prompt
    assert all(marker in prompt for marker in ("PERSONA", "STYLE", "PRIVATE", "OUTPUT"))


@pytest.mark.parametrize("requested", [None, "", "未配置风格", 3])
def test_missing_or_unknown_persona_style_keeps_base_style(monkeypatch, requested):
    monkeypatch.setattr(global_config.personality, "multiple_reply_style", ["轻松", "认真"])
    monkeypatch.setattr(global_config.personality, "multiple_probability", 1)
    random_sample = Mock()
    monkeypatch.setattr("src.chat.replyer.maisaka_generator_base.random.random", random_sample)
    assert BaseMaisakaReplyGenerator._select_temporary_reply_style({"persona_style": requested}) == ""
    random_sample.assert_not_called()


@pytest.mark.parametrize("retro", [False, True])
@pytest.mark.parametrize(
    "locale,example_notice", [("zh-CN", "不是真实聊天记录"), ("en-US", "not actual chat history"), ("ja-JP", "実際の会話履歴")],
)
def test_dialogue_examples_are_persona_context_not_chat_history(monkeypatch, retro, locale, example_notice):
    sample = "情境：拒绝\n用户：帮我写作业\n麦麦：我可以陪你理思路，代写就算啦"
    monkeypatch.setattr(global_config.personality, "dialogue_examples", [sample])
    monkeypatch.setattr(global_config.debug, "replyer_retro_prompt", retro)
    monkeypatch.setattr(
        "src.chat.replyer.maisaka_generator_base.get_chat_type_and_target_info", lambda session_id: (False, None),
    )
    generator = object.__new__(BaseMaisakaReplyGenerator)
    generator.chat_stream = SimpleNamespace(is_group_session=False)
    generator._load_prompt = load_prompt
    sources = []
    with use_locale(locale):
        items = generator._build_request_messages(
            chat_history=[], reply_message=None, reply_reason="", stream_id="test", prompt_sources=sources,
        )
    assert sample in get_item_text(items[0])
    assert example_notice in get_item_text(items[0])
    assert all(sample not in get_item_text(item) for item in items[1:])
    assert [source["source"] for source in sources].count("personality.dialogue_examples") == 1
    assert not any(source["source"] == "personality.multiple_reply_style" for source in sources)


@pytest.mark.asyncio
@pytest.mark.parametrize("sample,expected_style", [(0.1, "认真"), (0.9, "")])
@pytest.mark.parametrize("record_sources", [False, True])
async def test_persona_style_is_sampled_once_across_builds_and_retry(monkeypatch, sample, expected_style, record_sources):
    monkeypatch.setattr(global_config.personality, "multiple_reply_style", ["轻松", "认真"])
    monkeypatch.setattr(global_config.personality, "multiple_probability", 0.5)
    monkeypatch.setattr(global_config.debug, "replyer_retro_prompt", False)
    monkeypatch.setattr(global_config.debug, "save_maisaka_reasoning", record_sources)
    random_sample = Mock(return_value=sample)
    monkeypatch.setattr("src.chat.replyer.maisaka_generator_base.random.random", random_sample)
    monkeypatch.setattr(
        "src.chat.replyer.maisaka_generator_base.get_chat_type_and_target_info", lambda session_id: (False, None),
    )
    generator = object.__new__(BaseMaisakaReplyGenerator)
    generator.chat_stream = None
    generator.request_type = "maisaka.replyer"
    generator._load_prompt = load_prompt
    monkeypatch.setattr(generator, "_build_reply_context", AsyncMock(return_value=MaisakaReplyContext()))
    monkeypatch.setattr(generator, "_persist_reply_preview", Mock())
    build_request = Mock(wraps=generator._build_request_messages)
    monkeypatch.setattr(generator, "_build_request_messages", build_request)

    async def invoke_hook(name, **kwargs):
        original = deepcopy(kwargs)
        if name == "maisaka.replyer.before_request":
            kwargs["extra_prompt"] = "插件背景"
        if name == "maisaka.replyer.before_model_request":
            kwargs["items"][0]["parts"].append({"type": "text", "text": "本轮语气要求"})
        if name == "maisaka.replyer.after_response":
            kwargs["retry"] = kwargs["retry_count"] == 0
            kwargs["retry_reason"] = "测试重试"
        sources = collect_prompt_changes(original, kwargs, source="test.plugin", hook=name) if record_sources else []
        return SimpleNamespace(kwargs=kwargs, prompt_sources=sources)

    monkeypatch.setattr(generator, "_get_runtime_manager", lambda: SimpleNamespace(invoke_hook=invoke_hook))
    monkeypatch.setattr("src.desktop_pet.service.desktop_pet_service.notify_thinking", AsyncMock())

    async def run_on_main_loop(coro):
        return await coro

    monkeypatch.setattr("src.common.runtime_loop.run_on_main_loop", run_on_main_loop)

    async def generate_response(*, context_factory, options):
        await context_factory(SimpleNamespace())
        await context_factory(SimpleNamespace())
        return LLMResponseResult.from_portable_output(response="可以一起想想")

    generate = AsyncMock(side_effect=generate_response)
    generator.express_model = SimpleNamespace(task_name="replyer", generate_response_with_context=generate)
    success, result = await generator.generate_reply_with_context(
        chat_history=[], stream_id="test", reply_tool_args={"persona_style": "认真"},
    )
    assert success, result.error_message
    assert generate.await_count == 2
    random_sample.assert_called_once()
    assert build_request.call_count == 6
    assert {call.kwargs["temporary_reply_style"] for call in build_request.call_args_list} == {expected_style}
    if record_sources:
        assert [source["source"] for source in result.prompt_sources].count("personality.personality") == 1
        plugin_sources = [source for source in result.prompt_sources if source["source"] == "test.plugin"]
        assert [source["text"].strip() for source in plugin_sources] == ["插件背景", "本轮语气要求"]
    else:
        assert result.prompt_sources == []


@pytest.mark.asyncio
async def test_invalid_model_hook_items_do_not_record_injection_sources(monkeypatch):
    generator = object.__new__(BaseMaisakaReplyGenerator)
    generator.request_type = "maisaka.replyer"
    item = ContextItemBuilder().set_role(RoleType.System).add_text_content("原始人格").build()
    runtime = SimpleNamespace(invoke_hook=AsyncMock(return_value=SimpleNamespace(
        kwargs={"items": [{"item_type": "invalid"}], "item_schema_version": CONTEXT_ITEM_SCHEMA_VERSION},
        prompt_sources=[{"source": "test.plugin", "target": "system", "operation": "replace", "text": "无效改写"}],
    )))
    monkeypatch.setattr(generator, "_get_runtime_manager", lambda: runtime)
    sources = []
    result = await generator._invoke_before_model_request_hook(
        request_messages=[item], session_id="test", active_task_name="replyer", active_model_name=None,
        model_info=None, attempt=1, retry_count=0, reply_message=None, reply_reason="",
        selected_expression_ids=[], reply_tool_args={}, prompt_sources=sources,
    )
    assert result == [item] and sources == []
