"""按实际输入 Token 用量裁切上下文，保留条数模式和工具轮次。"""

from datetime import datetime
from types import SimpleNamespace
from typing import List
from unittest.mock import AsyncMock

import pytest

from src.chat.message_receive.message import SessionMessage
from src.common.data_models.llm_service_data_models import LLMResponseResult
from src.common.data_models.message_component_data_model import MessageSequence, TextComponent
from src.config.config import global_config
from src.llm_models.payload_content.tool_option import ToolCall
from src.maisaka.chat_loop_service import MaisakaChatLoopService
from src.maisaka.context.messages import LLMContextMessage, ModelOutputContextMessage, SessionBackedMessage, ToolResultMessage
from src.maisaka.context.post_processor import process_chat_history_after_cycle
from src.maisaka.reasoning_engine import MaisakaReasoningEngine
from src.maisaka.runtime import MaisakaHeartFlowChatting


def _history(size: int = 80) -> List[LLMContextMessage]:
    timestamp = datetime(2026, 11, 16, 12)
    return [
        SessionBackedMessage(
            raw_message=MessageSequence([TextComponent(str(index))]),
            visible_text=str(index), timestamp=timestamp, message_id=str(index),
            original_message=SessionMessage(message_id=str(index), timestamp=timestamp, platform="test"),
            source_kind="user",
        )
        for index in range(size)
    ]


@pytest.mark.parametrize("is_group", [True, False])
def test_token_mode_uses_only_current_chat_scope(monkeypatch, is_group):
    monkeypatch.setattr(global_config.chat, "use_token_limit", is_group)
    monkeypatch.setattr(global_config.chat, "private_use_token_limit", not is_group)
    messages = _history()
    selected, _ = MaisakaChatLoopService.select_llm_context_messages(
        messages, max_context_size=30, is_group_chat=is_group, enable_visual_message=False,
    )
    assert selected == messages
    selected_other, _ = MaisakaChatLoopService.select_llm_context_messages(
        messages, max_context_size=30, is_group_chat=not is_group, enable_visual_message=False,
    )
    assert len(selected_other) < len(messages)
    assert selected_other[-1] is messages[-1]


@pytest.mark.parametrize("prompt_tokens", [0, 15999])
def test_token_mode_does_not_trim_before_actual_threshold(prompt_tokens):
    messages = _history()
    result = process_chat_history_after_cycle(
        messages, max_context_size=30, max_context_tokens=16000, prompt_tokens=prompt_tokens,
    )
    assert result.history == messages
    assert result.removed_messages == []


def test_token_threshold_trims_below_count_limit_and_keeps_complete_tool_turn():
    messages = _history(20)
    response = LLMResponseResult.from_portable_output(tool_calls=[ToolCall("call-1", "lookup", {})])
    call = ModelOutputContextMessage(response.output_items[0])
    result_message = ToolResultMessage(
        content="result", timestamp=datetime.now(), tool_call_id="call-1", tool_name="lookup",
        logical_turn_id=call.output_item.meta.logical_turn_id,
    )
    messages[14:14] = [call, result_message]
    result = process_chat_history_after_cycle(
        messages, max_context_size=300, max_context_tokens=16000, prompt_tokens=16000,
    )
    assert result.history[-5:] == messages[-5:]
    assert len(result.removed_messages) > 0
    assert (call in result.history) == (result_message in result.history)
    assert result.removed_messages + result.history == messages


def test_count_mode_ignores_token_usage():
    messages = _history(20)
    result = process_chat_history_after_cycle(messages, max_context_size=300, prompt_tokens=1000000)
    assert result.history == messages
    assert result.removed_messages == []


@pytest.mark.asyncio
async def test_token_mode_reply_history_uses_active_window(monkeypatch):
    monkeypatch.setattr(global_config.chat, "private_use_token_limit", True)
    runtime = object.__new__(MaisakaHeartFlowChatting)
    runtime.chat_stream = SimpleNamespace(is_group_session=False)
    runtime._chat_history = _history()
    result = await runtime.build_retro_reply_history()
    assert result == runtime._chat_history


@pytest.mark.asyncio
async def test_committed_trim_consumes_prompt_token_usage(monkeypatch):
    service = MaisakaChatLoopService()
    service.last_planner_prompt_tokens = 16000
    runtime = SimpleNamespace(
        _chat_history=_history(40), _max_context_size=300, _max_context_tokens=16000,
        _chat_loop_service=service, _get_pending_wait_tool_call_ids=lambda: set(),
        _monitor_run_id="run", session_id="test", _log_history_trimmed=lambda *args: None,
        _trigger_trimmed_history_learning=AsyncMock(),
    )
    monkeypatch.setattr("src.maisaka.reasoning_engine.emit_flow_step", AsyncMock())
    engine = MaisakaReasoningEngine(runtime)
    cycle = SimpleNamespace(cycle_id="cycle", time_records={})
    await engine._post_process_chat_history_after_cycle(cycle, enable_compaction=False)
    assert len(runtime._chat_history) == 8
    assert service.last_planner_prompt_tokens == 0
    await engine._post_process_chat_history_after_cycle(cycle, enable_compaction=False)
    assert len(runtime._chat_history) == 8
    runtime._trigger_trimmed_history_learning.assert_awaited_once()
