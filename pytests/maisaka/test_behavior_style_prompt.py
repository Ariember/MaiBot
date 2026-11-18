from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.chat.replyer.document_generator import DocumentReplyGenerator
from src.chat.replyer.maisaka_generator_base import (
    REPLYER_MAX_HOOK_RETRIES,
    BaseMaisakaReplyGenerator,
    MaisakaReplyContext,
    select_persona_expressions,
)
from src.common.data_models.llm_service_data_models import LLMResponseResult
from src.common.prompt_templates import load_prompt
from src.config.config import global_config
from src.llm_models.payload_content.context_item import CONTEXT_ITEM_SCHEMA_VERSION, ContextItemBuilder, RoleType, get_item_text
from src.maisaka.builtin_tool import reply
from src.maisaka.chat_loop_service import MaisakaChatLoopService
from src.plugin_runtime.host.hook_dispatcher import HookDispatchResult
from src.plugin_runtime.prompt_sources import collect_prompt_changes


def test_reply_length_instructions_use_chinese() -> None:
    build_style = BaseMaisakaReplyGenerator._build_requested_reply_style_message
    assert '一到两句' in build_style("简短表达")
    assert '简洁' in build_style("正常回复")
    assert '关键细节' in build_style("长回复")
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
def test_attention_drift_follows_live_config_in_planner_and_replyer(
    monkeypatch: pytest.MonkeyPatch, prompt_name: str, is_group_chat: bool
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
    monkeypatch.setattr(config, "enabled", False)
    baseline = build_prompt()
    if prompt_name == "maisaka_replyer":
        assert "测试人设" in baseline
    assert '注意力漂移风格：' not in baseline
    monkeypatch.setattr(config, "enabled", True)
    assert build_prompt().count('注意力漂移风格：') == 1
    monkeypatch.setattr(config, "enabled", False)
    assert build_prompt() == baseline


@pytest.mark.parametrize("prompt_name", ["maisaka_chat", "maisaka_chat_focus"])
def test_planner_personality_precedes_behavior_style(
    monkeypatch: pytest.MonkeyPatch, prompt_name: str
) -> None:
    monkeypatch.setattr(global_config.personality, "personality", "核心人格测试标记")
    monkeypatch.setattr(global_config.personality, "behavior_style", "行为风格测试标记")
    service = MaisakaChatLoopService()
    monkeypatch.setattr(service, "_get_chat_prompt_name", lambda: prompt_name)

    prompt = service._build_chat_system_prompt()

    assert prompt.index("核心人格测试标记") < prompt.index("行为风格测试标记")


def test_reply_tool_offers_configured_scene_and_slang_choices(monkeypatch):
    monkeypatch.setattr(reply, "build_reply_extensions_schema", lambda context: None)
    monkeypatch.setattr(global_config.personality, "dialogue_examples", [" 安慰朋友 ", "", "黑话：破防", "安慰朋友"])
    schema = reply.get_tool_spec().parameters_schema
    choices = schema["properties"]["persona_expressions"]
    assert choices["type"] == "array"
    assert choices["items"]["enum"] == ["安慰朋友", "黑话：破防"]
    assert "persona_expressions" not in schema["required"]
    assert "persona_style" not in schema["properties"]
    monkeypatch.setattr(global_config.personality, "dialogue_examples", [])
    assert "persona_expressions" not in reply.get_tool_spec().parameters_schema["properties"]


def test_replyer_template_does_not_assume_group_chat():
    prompt = load_prompt(
        "maisaka_replyer", identity="PERSONA", reply_style="STYLE", group_chat_attention_block="PRIVATE",
        replyer_output_instruction="OUTPUT",
    )
    assert 'QQ群' not in prompt
    assert all(marker in prompt for marker in ("PERSONA", "STYLE", "PRIVATE", "OUTPUT"))


@pytest.mark.parametrize("requested", [None, "", "安慰朋友", 3, ["未配置表达"], [3]])
def test_invalid_persona_expressions_are_rejected(monkeypatch, requested):
    monkeypatch.setattr(global_config.personality, "dialogue_examples", ["安慰朋友", "黑话：破防"])
    with pytest.raises(ValueError, match="persona_expressions"):
        select_persona_expressions({"persona_expressions": requested})


def test_persona_expressions_keep_order_without_duplicates(monkeypatch):
    monkeypatch.setattr(global_config.personality, "dialogue_examples", ["安慰朋友", "黑话：破防"])
    assert select_persona_expressions() == []
    assert select_persona_expressions({"persona_expressions": []}) == []
    assert select_persona_expressions({"persona_expressions": [" 黑话：破防 ", "安慰朋友", "黑话：破防"]}) == [
        "黑话：破防", "安慰朋友",
    ]


@pytest.mark.asyncio
async def test_reply_tool_rejects_unknown_persona_expressions(monkeypatch):
    monkeypatch.setattr(global_config.personality, "dialogue_examples", ["安慰朋友"])
    tool_ctx = SimpleNamespace(build_failure_result=Mock(return_value="invalid selection"))
    result = await reply.execute_reply(
        tool_ctx, {"reply_reference": "安慰当前朋友", "persona_expressions": ["未知"]}, call_id="test",
    )
    assert result == "invalid selection"
    assert "persona_expressions" in tool_ctx.build_failure_result.call_args.args[1]


@pytest.mark.parametrize("mode", ["modern", "retro", "document"])
@pytest.mark.parametrize("selected", [False, True])
def test_only_selected_scene_and_slang_reach_replyer(monkeypatch, mode, selected):
    sample = "情境：拒绝\n用户：帮我写作业\n麦麦：我可以陪你理思路，代写就算啦"
    slang = "黑话：破防，形容心态受到冲击"
    unselected = "情景：祝贺升职"
    monkeypatch.setattr(global_config.personality, "dialogue_examples", [sample, slang, unselected])
    monkeypatch.setattr(global_config.personality, "reply_style", "基础表达标记")
    monkeypatch.setattr(global_config.debug, "replyer_retro_prompt", mode == "retro")
    monkeypatch.setattr(
        "src.chat.replyer.maisaka_generator_base.get_chat_type_and_target_info", lambda session_id: (False, None),
    )
    generator = object.__new__(DocumentReplyGenerator if mode == "document" else BaseMaisakaReplyGenerator)
    generator.chat_stream = SimpleNamespace(is_group_session=False)
    generator._load_prompt = load_prompt
    sources = []
    items = generator._build_request_messages(
        chat_history=[], reply_message=None, reply_reason="回答当前问题", stream_id="test", prompt_sources=sources,
        reply_requirements="直接回答",
        reply_tool_args={"persona_expressions": [sample, slang]} if selected else {},
    )
    text = "\n".join(get_item_text(item) for item in items)
    assert "基础表达标记" in text
    assert unselected not in text
    assert (sample in text) == selected
    assert (slang in text) == selected
    assert ('不是真实聊天记录' in text) == selected
    assert [source["source"] for source in sources].count("personality.dialogue_examples") == int(selected)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("record_sources", "final_review"),
    [
        (False, "passed"), (True, "passed"), (False, "error"), (False, "rejected"),
        (False, "rewritten"), (False, "different_model"), (False, "retro_repeat"), (False, "retro_passed"),
    ],
)
async def test_replyer_keeps_prompt_guidance_and_records_only_validated_retries(monkeypatch, record_sources, final_review):
    retro = final_review.startswith("retro_")
    first_response = "给我发个句号吧" if retro else "我会逐条讲解这个问题"
    monkeypatch.setattr(global_config.personality, "dialogue_examples", ["安慰朋友", "黑话：破防"])
    monkeypatch.setattr(global_config.debug, "replyer_retro_prompt", retro)
    monkeypatch.setattr(global_config.debug, "save_maisaka_reasoning", record_sources)
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
        errors = []
        if name == "maisaka.replyer.before_request":
            kwargs["extra_prompt"] = "插件背景"
        if name == "maisaka.replyer.before_model_request":
            kwargs["items"][0]["parts"].append({"type": "text", "text": "本轮语气要求"})
        if name == "maisaka.replyer.after_response" and not retro:
            kwargs["retry"] = kwargs["retry_count"] == 0 or final_review == "rejected"
            if kwargs["retry"]:
                kwargs["retry_reason"] = "对方只需要简短的回应"
            elif final_review == "error":
                errors.append("审核异常")
            elif final_review == "rewritten":
                kwargs["response"] = "已由审核插件代写"
        sources = collect_prompt_changes(original, kwargs, source="test.plugin", hook=name) if record_sources else []
        return HookDispatchResult(hook_name=name, kwargs=kwargs, errors=errors, prompt_sources=sources)

    monkeypatch.setattr(generator, "_get_runtime_manager", lambda: SimpleNamespace(invoke_hook=invoke_hook))
    monkeypatch.setattr("src.desktop_pet.service.desktop_pet_service.notify_thinking", AsyncMock())

    async def run_on_main_loop(coro):
        return await coro

    monkeypatch.setattr("src.common.runtime_loop.run_on_main_loop", run_on_main_loop)

    async def generate_response(*, context_factory, options):
        await context_factory(SimpleNamespace())
        await context_factory(SimpleNamespace())
        if generate.await_count == 1:
            return LLMResponseResult.from_portable_output(response=first_response, model_name="test-model")
        model = "other-model" if final_review == "different_model" else "test-model"
        response = "可以发一个句号吗？" if final_review == "retro_repeat" else "可以一起想想"
        return LLMResponseResult.from_portable_output(response=response, model_name=model)

    generate = AsyncMock(side_effect=generate_response)
    generator.express_model = SimpleNamespace(task_name="replyer", generate_response_with_context=generate)
    experience = "【回复经验】朋友提出简短的问题时，先用一句话回答。"
    success, result = await generator.generate_reply_with_context(
        chat_history=[], stream_id="test", reply_tool_args={"persona_expressions": ["安慰朋友", "黑话：破防"]},
        experience_guidance=experience,
    )
    assert success, result.error_message
    attempt_count = REPLYER_MAX_HOOK_RETRIES + 1 if final_review == "rejected" else 2
    assert generate.await_count == attempt_count
    assert build_request.call_count == 3 * attempt_count
    assert all(experience in call.kwargs["reply_requirements"] for call in build_request.call_args_list)
    assert result.metrics.extra["replyer_retry_events"][0]["rejected_response"] == first_response
    assert result.metrics.extra.get("replyer_retry_accepted", False) is (final_review in {"passed", "retro_passed"})
    selected_prompts = {call.kwargs["persona_expressions_prompt"] for call in build_request.call_args_list}
    assert len(selected_prompts) == 1
    selected_prompt = next(iter(selected_prompts))
    assert "安慰朋友" in selected_prompt and "黑话：破防" in selected_prompt
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
