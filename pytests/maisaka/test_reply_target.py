"""无目标主动发言与真实消息回复共用发送链路。"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.common.data_models.message_component_data_model import MessageSequence, TextComponent
from src.common.data_models.reply_generation_data_models import LLMCompletionResult, ReplyGenerationResult
from src.core.tooling import ToolExecutionResult
from src.maisaka import reasoning_engine
from src.maisaka.builtin_tool import reply
from src.maisaka.builtin_tool.context import PostProcessedReplyMessage
from src.maisaka.context.messages import InternalContextMessage
from src.maisaka.reasoning_engine import CycleRuntimeState, MaisakaReasoningEngine


@pytest.fixture
def reply_context(monkeypatch):
    target = SimpleNamespace(
        message_id="message",
        message_info=SimpleNamespace(
            user_info=SimpleNamespace(user_id="200", user_nickname="用户", user_cardname=None),
        ),
    )
    runtime = SimpleNamespace(
        session_id="test",
        chat_stream=SimpleNamespace(platform="test", is_group_session=False),
        _chat_history=[
            InternalContextMessage(
                raw_message=MessageSequence([TextComponent("主动问候")]),
                visible_text="主动问候",
                timestamp=datetime.now(),
                message_id="proactive:task",
            )
        ],
        find_source_message_by_id=Mock(side_effect=lambda message_id: target if message_id == "message" else None),
        log_prefix="test",
        _update_stage_status=Mock(),
        record_planner_reply=Mock(),
    )
    tool_ctx = SimpleNamespace(
        runtime=runtime,
        build_failure_result=Mock(return_value={"success": False}),
        build_success_result=Mock(return_value={"success": True}),
        post_process_reply_message_items_async=AsyncMock(
            return_value=[PostProcessedReplyMessage(sequence=MessageSequence([TextComponent("你好")]))]
        ),
    )
    generate = AsyncMock(
        return_value=(
            True,
            ReplyGenerationResult(completion=LLMCompletionResult(response_text="你好")),
        )
    )
    monkeypatch.setattr(
        reply.replyer_manager, "get_replyer", lambda **kwargs: SimpleNamespace(generate_reply_with_context=generate)
    )
    monkeypatch.setattr(
        reply,
        "ReplyExtensionExecution",
        lambda **kwargs: SimpleNamespace(prepare=AsyncMock(), targets=[], reply_id="test"),
    )
    monkeypatch.setattr(reply.config_module.global_config.debug, "replyer_retro_prompt", False)
    monkeypatch.setattr(reply.config_module.global_config.chat.reply_style, "private_quote_frequency", "never")
    monkeypatch.setattr(reply, "_invoke_before_post_process_hook", AsyncMock(return_value=("你好", {})))
    monkeypatch.setattr(reply, "is_bot_self", lambda *args: False)
    send = AsyncMock(return_value=SimpleNamespace(message_id="sent"))
    monkeypatch.setattr(reply.send_service, "_send_to_target_with_message", send)
    return SimpleNamespace(context=tool_ctx, target=target, generate=generate, send=send)


def test_reply_schema_allows_omitted_target(monkeypatch):
    monkeypatch.setattr(reply, "build_reply_extensions_schema", lambda context: None)
    assert reply.get_tool_spec().parameters_schema["required"] == ["reply_reference"]


@pytest.mark.asyncio
@pytest.mark.parametrize("msg_id", [None, "", "proactive:task", "message"])
async def test_reply_sends_to_current_session_with_optional_target(reply_context, msg_id):
    args = {"reply_reference": "主动问候"}
    if msg_id is not None:
        args["msg_id"] = msg_id
    target = reply_context.target if msg_id == "message" else None

    result = await reply.execute_reply(reply_context.context, args, call_id="reply")

    assert result == {"success": True}
    reply_context.context.build_failure_result.assert_not_called()
    assert reply_context.generate.call_args.kwargs["reply_message"] is target
    send_args = reply_context.send.call_args.kwargs
    assert send_args["stream_id"] == "test"
    assert send_args["reply_message"] is target
    assert send_args["set_reply"] is False
    content = reply_context.context.build_success_result.call_args.kwargs["structured_content"]
    assert content["msg_id"] == ("message" if target else "")
    assert content["target_user_name"] == ("用户" if target else "")
    assert args.get("msg_id") == msg_id


@pytest.mark.asyncio
async def test_unknown_target_is_not_changed_to_proactive_reply(reply_context):
    result = await reply.execute_reply(
        reply_context.context,
        {"msg_id": "proactive:missing", "reply_reference": "问候"},
        call_id="reply",
    )
    assert result == {"success": False}
    assert "未找到要回复的目标消息" in reply_context.context.build_failure_result.call_args.args[1]
    reply_context.generate.assert_not_called()
    reply_context.send.assert_not_called()


@pytest.mark.asyncio
async def test_snapshot_must_match_target_id(reply_context):
    with pytest.raises(ValueError, match="消息 ID 与回复参数不一致"):
        await reply.execute_reply(
            reply_context.context,
            {"reply_reference": "问候"},
            call_id="reply",
            target_message=reply_context.target,
        )
    reply_context.send.assert_not_called()


@pytest.mark.asyncio
async def test_planner_text_can_reply_without_real_message(monkeypatch):
    runtime = SimpleNamespace(
        session_id="test",
        _update_stage_status=Mock(),
        _chat_loop_service=SimpleNamespace(planner_request_snapshot=object()),
    )
    execute = AsyncMock(return_value=ToolExecutionResult(tool_name="reply", success=True, content="已发言"))
    monkeypatch.setattr(reasoning_engine, "execute_reply", execute)
    state = CycleRuntimeState()

    await MaisakaReasoningEngine(runtime)._reply_from_planner_content(
        "主动问候",
        SimpleNamespace(time_records={}),
        state,
    )

    assert execute.call_args.args[1] == {"msg_id": "", "reply_reference": "主动问候"}
    assert execute.call_args.kwargs["target_message"] is None
    assert callable(execute.call_args.kwargs["supplement_runner"])
    assert state.cycle_end.reason == "planner_reply_end"
