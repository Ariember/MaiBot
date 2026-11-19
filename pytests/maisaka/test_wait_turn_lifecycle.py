from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import asyncio
import time

import pytest

from src.maisaka.reasoning_engine import CycleEnd, CycleRuntimeState, MaisakaReasoningEngine
from src.maisaka.runtime import MaisakaHeartFlowChatting
from src.maisaka.turn_trigger.scheduler import MessageTurnScheduler


def _build_runtime_stub() -> MaisakaHeartFlowChatting:
    runtime = object.__new__(MaisakaHeartFlowChatting)
    runtime._agent_state = runtime._STATE_RUNNING
    runtime._pending_wait_tool_call_id = None
    runtime._pending_wait_logical_turn_id = None
    runtime._pending_wait_started_at = None
    runtime._pending_wait_seconds = None
    runtime._wait_timeout_task = None
    runtime._proactive_trigger_message = None
    runtime._proactive_logical_turn_id = None
    runtime._internal_turn_queue = asyncio.Queue()
    runtime._mark_message_turn_unscheduled = lambda: None
    runtime._cancel_deferred_message_turn_task = lambda: None
    return runtime


def test_wait_pause_resume_completes_original_logical_turn() -> None:
    runtime = _build_runtime_stub()
    runtime._enter_wait_state(
        seconds=None,
        tool_call_id="wait-call-1",
        logical_turn_id="turn-wait-1",
    )
    runtime._pending_wait_started_at = time.time() - 1

    assert runtime._get_pending_wait_tool_call_ids() == {"wait-call-1"}
    runtime._enter_running_state()
    engine = object.__new__(MaisakaReasoningEngine)
    engine._runtime = runtime
    completed = engine._build_wait_completed_message(has_new_messages=True)

    assert completed.tool_call_id == "wait-call-1"
    assert completed.logical_turn_id == "turn-wait-1"
    assert completed.timestamp <= datetime.now()
    assert runtime._get_pending_wait_tool_call_ids() == set()


def test_wait_requires_registered_call_and_turn() -> None:
    runtime = _build_runtime_stub()
    with pytest.raises(ValueError, match="tool_call_id 和 logical_turn_id"):
        runtime._enter_wait_state(tool_call_id="wait-call-1", logical_turn_id=None)
    with pytest.raises(RuntimeError, match="不存在可补齐"):
        runtime._consume_pending_wait_state()


def test_proactive_switch_trigger_carries_source_logical_turn() -> None:
    runtime = _build_runtime_stub()
    runtime._agent_state = runtime._STATE_WAIT
    trigger = object()

    runtime._queue_proactive_turn(trigger, logical_turn_id="turn-switch-1")  # type: ignore[arg-type]

    assert runtime._agent_state == runtime._STATE_RUNNING
    assert runtime._consume_proactive_trigger_message() is trigger
    assert runtime._consume_proactive_logical_turn_id() == "turn-switch-1"
    assert runtime._internal_turn_queue.get_nowait() == "proactive"


@pytest.mark.asyncio
async def test_queued_proactive_turn_resumes_wait_entered_after_enqueue() -> None:
    runtime = _build_runtime_stub()
    trigger = object()
    # 主动任务先排队，当前 Planner 随后调用 wait，再消费已排队的主动任务。
    runtime._queue_proactive_turn(trigger, logical_turn_id="turn-proactive")  # type: ignore[arg-type]
    runtime._enter_wait_state(tool_call_id="wait-call", logical_turn_id="turn-wait")
    runtime._is_reply_frequency_silent = lambda: False
    runtime._has_pending_messages = lambda: False
    runtime._clear_focus_cooldown_wakeup_scheduled = lambda: None
    runtime.restore_proactive_user_context = AsyncMock()
    runtime._chat_history = []
    engine = object.__new__(MaisakaReasoningEngine)
    engine._runtime = runtime
    engine._emit_flow_step = AsyncMock()

    context = await engine._prepare_turn_start_context(runtime._internal_turn_queue.get_nowait())

    assert context.trigger_message is trigger
    assert context.logical_turn_id == "turn-wait"
    assert runtime._chat_history[0].tool_call_id == "wait-call"
    assert runtime._get_pending_wait_tool_call_ids() == set()
    assert runtime._agent_state == runtime._STATE_RUNNING


@pytest.mark.asyncio
async def test_timeout_queued_during_debounce_cannot_complete_next_wait() -> None:
    runtime = _build_runtime_stub()
    runtime._running = True
    runtime.log_prefix = "[test]"
    runtime._is_reply_frequency_silent = lambda: False
    runtime._clear_focus_cooldown_wakeup_scheduled = lambda: None
    runtime._chat_history = []
    runtime.message_cache = []
    runtime._last_processed_index = 0
    runtime._fixed_message_debouncer = Mock()
    runtime._update_stage_status = Mock()
    engine = MaisakaReasoningEngine(runtime)
    engine._ingest_messages = AsyncMock()

    runtime._queue_proactive_turn(object())
    runtime._enter_wait_state(tool_call_id="first", logical_turn_id="turn")
    runtime.message_cache.append(object())

    async def finish_debounce():
        await runtime._schedule_wait_timeout(0, "first")

    runtime._wait_for_message_quiet_period = finish_debounce
    context = await engine._prepare_turn_start_context(runtime._internal_turn_queue.get_nowait())
    assert context.logical_turn_id == "turn"
    assert runtime._chat_history[-1].tool_call_id == "first"
    runtime._enter_wait_state(tool_call_id="second", logical_turn_id="turn")
    context = await engine._prepare_turn_start_context(runtime._internal_turn_queue.get_nowait())
    assert context.trigger_message is None
    assert runtime._agent_state == runtime._STATE_WAIT
    assert runtime._get_pending_wait_tool_call_ids() == {"second"}
    assert len(runtime._chat_history) == 1


@pytest.mark.parametrize(("frequency", "limit"), [(0.49, 8), (0.5, 16)])
@pytest.mark.asyncio
async def test_group_timed_wait_uses_original_round_budget(monkeypatch, frequency, limit) -> None:
    runtime = _build_runtime_stub()
    runtime.chat_stream = SimpleNamespace(is_group_session=True)
    runtime._get_effective_reply_frequency = lambda: frequency
    runtime._is_reply_frequency_silent = lambda: False
    runtime.log_prefix = "[test]"
    runtime._running = True
    runtime._consecutive_wait_count = 0
    runtime._monitor_run_id = "run"
    runtime.session_id = "group"
    runtime.message_cache = [object()]
    runtime._last_processed_index = 1
    runtime._chat_history = []
    runtime._idle_backoff = Mock()
    runtime._prepare_tool_prompt_records = Mock(return_value=[])
    runtime._render_context_usage_panel = Mock()
    runtime._focus_group = None
    runtime._message_turn_scheduled = False
    runtime._message_turn_scheduler = MessageTurnScheduler(runtime)
    runtime._get_message_quiet_period_remaining_seconds = lambda: 0.0
    runtime._has_forced_turn_trigger = lambda: False
    runtime._idle_backoff.get_delay_seconds.return_value = 0.0
    evaluate = Mock(return_value=SimpleNamespace(decision="wait", detail="继续等待"))
    monkeypatch.setattr(runtime._message_turn_scheduler._dynamic_reply_gate, "evaluate", evaluate)
    monkeypatch.setattr("src.maisaka.runtime.global_config.chat.reply_timing.planner_message_steering", False)
    engine = MaisakaReasoningEngine(runtime)
    cycle = SimpleNamespace(cycle_id=1, time_records={})
    engine._end_cycle = AsyncMock(return_value=cycle)
    monkeypatch.setattr("src.maisaka.reasoning_engine.emit_planner_snapshot", AsyncMock())
    assert engine._start_planner_turn("turn") == 0
    assert runtime._max_internal_rounds == limit
    # 频率热更新只在下个逻辑回合生效。
    runtime._get_effective_reply_frequency = lambda: 1.0
    for index in range(limit):
        call_id = f"wait-{index}"
        runtime._enter_wait_state(tool_call_id=call_id, logical_turn_id="turn")
        await runtime._schedule_wait_timeout(0, call_id)
        assert runtime._agent_state == runtime._STATE_WAIT
        if index + 1 == limit:
            runtime.message_cache.append(object())
            runtime._schedule_message_turn()
            evaluate.assert_not_called()
        end = await engine._finalize_cycle(
            cycle_detail=cycle, round_index=index, state=CycleRuntimeState(cycle_end=CycleEnd("tool_pause:wait", ""))
        )
        context = await engine._prepare_turn_start_context(runtime._internal_turn_queue.get_nowait())
        if index + 1 < limit:
            assert end.reason == "tool_pause:wait"
            assert context.trigger_message is runtime.message_cache[-1]
            assert runtime._agent_state == runtime._STATE_RUNNING
            assert engine._start_planner_turn(context.logical_turn_id) == index + 1
        else:
            assert end.reason == "max_rounds"
            assert context.trigger_message is None
            assert runtime._agent_state == runtime._STATE_STOP
        assert runtime._chat_history[-1].tool_call_id == call_id
        assert runtime._get_pending_wait_tool_call_ids() == set()
    assert len(runtime._chat_history) == limit
    assert "等待已取消" in runtime._chat_history[-1].content
    evaluate.assert_called_once_with(pending_messages=runtime.message_cache[-1:], frequency=1.0)
    assert engine._start_planner_turn("next-turn") == 0
    assert runtime._max_internal_rounds == 16
