from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from pydantic import ValidationError

import asyncio
import pytest

from src.common.data_models.llm_service_data_models import LLMResponseResult
from src.common.data_models.message_component_data_model import MessageSequence, TextComponent
from src.common.data_models.reply_generation_data_models import LLMCompletionResult, ReplyGenerationResult
from src.common.prompt_i18n import list_prompt_templates, load_prompt
from src.config.model_configs import ModelInfo
from src.llm_models.model_client.base_client import ResponseRequest
from src.llm_models.payload_content.context_item import ContextItemBuilder, RoleType, get_item_text
from src.maisaka import reply_supplement
from src.maisaka.builtin_tool import reply
from src.maisaka.builtin_tool.context import PostProcessedReplyMessage
from src.maisaka.context.compaction import PlannerRequestSnapshot


@pytest.mark.parametrize("locale", ["zh-CN", "en-US", "ja-JP"])
def test_retry_prompt_has_localized_metadata_and_error_feedback(locale):
    metadata = list_prompt_templates(locale=locale)["reply_supplement_retry"].metadata
    assert metadata.display_name and metadata.description
    assert "ValidationError" in load_prompt("reply_supplement_retry", locale=locale, error="ValidationError")


@pytest.mark.asyncio
@pytest.mark.parametrize("retry_succeeds", [True, False])
async def test_invalid_plan_is_regenerated_with_feedback(monkeypatch, retry_succeeds):
    request = ResponseRequest(
        model_info=ModelInfo(model_type="llm", model_identifier="test", name="test", api_provider="test"),
        context_items=[ContextItemBuilder().set_role(RoleType.System).add_text_content("Planner prefix").build()],
    )
    snapshot = PlannerRequestSnapshot(request=request, history=())
    resources = reply_supplement.SupplementResources({}, {}, {}, False, False, False)
    monkeypatch.setattr(reply_supplement.SupplementResources, "capture", lambda *args: resources)
    monkeypatch.setattr(reply_supplement.global_config.debug, "save_maisaka_reasoning", False)
    responses = ["刚睡醒，看到群里给我看饿了都。", '{"msg_id":null,"parts":[{"type":"reply"}]}']
    if not retry_succeeds:
        responses[1] = "还是聊天正文"
    requests = []

    async def generate(self, current_request):
        requests.append(current_request)
        return LLMResponseResult(output_items=(
            ContextItemBuilder().set_role(RoleType.Assistant).add_text_content(responses[len(requests) - 1]).build(),
        ))

    monkeypatch.setattr(reply_supplement.LLMServiceClient, "generate_response_from_snapshot", generate)
    if retry_succeeds:
        supplement = await reply_supplement.generate_reply_supplement(snapshot, "发言指导", "test", False)
        assert supplement.components == [None]
    else:
        with pytest.raises(ValidationError):
            await reply_supplement.generate_reply_supplement(snapshot, "发言指导", "test", False)
    assert len(requests) == 2
    assert "ValidationError" in get_item_text(requests[1].context_items[-1])
    assert all(item.response_format is None for item in requests)
    assert len(request.context_items) == 1


@pytest.mark.asyncio
async def test_cancellation_does_not_regenerate(monkeypatch):
    generate = AsyncMock(side_effect=asyncio.CancelledError)
    monkeypatch.setattr(reply_supplement, "_generate_reply_supplement_once", generate)
    with pytest.raises(asyncio.CancelledError):
        await reply_supplement.generate_reply_supplement(None, "指导", "test", False)
    assert generate.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("supplement_kind", ["failed", "quote", "no_quote"])
async def test_supplement_failure_keeps_body_and_quote_respects_frequency(monkeypatch, supplement_kind):
    body = ReplyGenerationResult(completion=LLMCompletionResult(response_text="正文已生成"))
    generated = asyncio.Event()
    target = SimpleNamespace(
        message_id="message", message_info=SimpleNamespace(user_info=SimpleNamespace(
            user_id="200", user_nickname="用户", user_cardname=None,
        )),
    )

    async def generate_body(**kwargs):
        await generated.wait()
        return True, body

    async def generate_supplement():
        generated.set()
        if supplement_kind == "failed":
            raise ValueError("重生成后仍无效")
        plan = reply_supplement.ReplySupplementPlan.model_validate({
            "msg_id": "message" if supplement_kind == "quote" else None, "parts": [{"type": "reply"}],
        })
        return reply_supplement.ReplySupplement(
            plan, target if supplement_kind == "quote" else None, [None], {"plan": plan.model_dump()},
        )

    runtime = SimpleNamespace(
        session_id="test", chat_stream=SimpleNamespace(platform=reply.CLI_PLATFORM_NAME), _chat_history=[],
        log_prefix="test", _update_stage_status=Mock(), record_planner_reply=Mock(),
    )
    tool_ctx = SimpleNamespace(
        runtime=runtime, build_failure_result=Mock(), build_success_result=Mock(return_value={"success": True}),
        append_guided_reply_to_chat_history=Mock(),
        post_process_reply_message_items_async=AsyncMock(return_value=[PostProcessedReplyMessage(
            sequence=MessageSequence([TextComponent("正文已生成")]),
        )]),
    )
    extension = SimpleNamespace(prepare=AsyncMock(), targets=[], reply_id="test")
    monkeypatch.setattr(reply, "ReplyExtensionExecution", Mock(return_value=extension))
    monkeypatch.setattr(reply.replyer_manager, "get_replyer", Mock(return_value=SimpleNamespace(
        generate_reply_with_context=generate_body,
    )))
    monkeypatch.setattr(reply.config_module.global_config.debug, "replyer_retro_prompt", False)
    monkeypatch.setattr(reply, "_invoke_before_post_process_hook", AsyncMock(return_value=("正文已生成", {})))
    monkeypatch.setattr(reply, "is_bot_self", lambda *args: False)
    render = Mock()
    monkeypatch.setattr(reply, "render_cli_message", render)
    quote = AsyncMock(return_value=(False, 0.0))
    monkeypatch.setattr(reply, "_resolve_reply_quote", quote)

    result = await reply.execute_reply(
        tool_ctx, {"msg_id": "message", "reply_reference": "指导"}, call_id="test",
        target_message=target, supplement_runner=generate_supplement,
    )

    assert result == {"success": True}
    render.assert_called_once_with("正文已生成")
    tool_ctx.build_failure_result.assert_not_called()
    assert quote.await_count == int(supplement_kind != "no_quote")
    assert not tool_ctx.build_success_result.call_args.kwargs["structured_content"]["effective_set_quote"]
