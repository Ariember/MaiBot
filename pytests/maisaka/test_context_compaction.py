from datetime import datetime
from unittest.mock import Mock

import asyncio
import json
import pytest

from src.agent.config import AgentConfig
from src.agent.planner import ACPPlannerSnapshot
from src.common.data_models.llm_service_data_models import LLMResponseResult
from src.common.prompt_i18n import list_prompt_templates, load_prompt
from src.config.model_configs import ModelInfo
from src.llm_models.model_client.base_client import ResponseRequest
from src.llm_models.payload_content.context_item import ContextItemBuilder, RoleType, get_item_text
from src.llm_models.payload_content.tool_option import ToolCall
from src.maisaka.context import compaction


def _response(**fields):
    state = {name: [] for name in compaction.STATE_LABELS}
    state.update(topics=["会议改期"], **fields)
    return LLMResponseResult.from_portable_output(response=json.dumps(state, ensure_ascii=False))


@pytest.fixture(params=[False, True], ids=["native", "acp"])
def summary_request(request, monkeypatch):
    prefix = [ContextItemBuilder().set_role(RoleType.System).add_text_content("Planner prefix").build()]
    if request.param:
        original = ACPPlannerSnapshot(config=AgentConfig(), context_items=prefix, history_item_ids=["history"])
    else:
        original = ResponseRequest(
            model_info=ModelInfo(model_type="llm", model_identifier="test", name="test", api_provider="test"),
            context_items=prefix,
        )
    requests = []
    responses = Mock()

    async def generate(current):
        requests.append(list(current))
        return responses()

    async def native_generate(self, current):
        return await generate(current.context_items)

    async def acp_generate(config, session_id, items, tools, *, history_item_ids):
        assert tools == []
        assert history_item_ids == ["history"]
        return await generate(items)

    monkeypatch.setattr(compaction.LLMServiceClient, "generate_response_from_snapshot", native_generate)
    monkeypatch.setattr(compaction, "generate_planner_response", acp_generate)
    preview = Mock()
    monkeypatch.setattr(compaction, "save_compaction_prompt_preview", preview)
    removed = compaction.ContextSummaryMessage(content="会议改期到明天", timestamp=datetime.now())

    async def build():
        return await compaction.build_context_summary(
            [removed],
            planner_snapshot=compaction.PlannerRequestSnapshot(request=original, history=()),
            previous_summary=None,
            recent_messages=[],
            session_id="test",
            max_summary_chars=120,
        )

    return build, responses, requests, original, preview, removed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "first_response",
    [
        LLMResponseResult.from_portable_output(response="我先看看下一步该做什么"),
        LLMResponseResult.from_portable_output(response='{"topics":["会议改期"]}'),
        LLMResponseResult.from_portable_output(response=json.dumps({name: [] for name in compaction.STATE_LABELS})),
        _response(background=["过长" * 120]),
        LLMResponseResult.from_portable_output(tool_calls=[ToolCall("stop-1", "stop", {})]),
    ],
)
async def test_invalid_summary_retries_without_replaying_model_actions(summary_request, first_response):
    build, responses, requests, original, preview, removed = summary_request
    responses.side_effect = [first_response, _response()]
    result = await build()
    assert result.content == "当前话题:\n- 会议改期"
    assert result.timestamp == removed.timestamp
    assert len(requests) == 2
    assert requests[1][:-1] == requests[0]
    assert get_item_text(requests[1][-1]) == load_prompt("context_compaction_retry", max_summary_chars=120)
    assert len(original.context_items) == 1
    assert preview.call_count == 2


@pytest.mark.asyncio
async def test_valid_summary_does_not_retry(summary_request):
    build, responses, requests, _, _, _ = summary_request
    responses.return_value = _response()
    await build()
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_second_invalid_summary_still_obeys_character_budget(summary_request):
    build, responses, requests, _, _, _ = summary_request
    responses.return_value = _response(background=["过长" * 120])
    with pytest.raises(ValueError, match="超过字符预算"):
        await build()
    assert len(requests) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [TimeoutError("请求超时"), asyncio.CancelledError()])
async def test_provider_failure_and_cancellation_do_not_regenerate(summary_request, error):
    build, responses, requests, _, _, _ = summary_request
    responses.side_effect = error
    with pytest.raises(type(error)):
        await build()
    assert len(requests) == 1


@pytest.mark.parametrize("locale", ["zh-CN", "en-US", "ja-JP"])
def test_retry_prompt_preserves_budget_and_localized_metadata(locale):
    metadata = list_prompt_templates(locale=locale)["context_compaction_retry"].metadata
    assert metadata.display_name and metadata.description
    prompt = load_prompt("context_compaction_retry", locale=locale, max_summary_chars=120)
    assert "120" in prompt
    assert all(name in prompt for name in compaction.STATE_LABELS)
