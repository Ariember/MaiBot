"""联网查询的并发上限、串行边界与结果归属。"""

from types import SimpleNamespace
from typing import Awaitable, Callable, List, Optional
from unittest.mock import AsyncMock, Mock

import asyncio
import pytest

from src.common.data_models.llm_service_data_models import LLMResponseResult
from src.config.config import global_config
from src.core.tooling import ToolExecutionResult, ToolInvocation, ToolSpec
from src.llm_models.payload_content.tool_option import ToolCall
from src.maisaka.builtin_tool import subagent
from src.maisaka.builtin_tool.context import BuiltinToolRuntimeContext
from src.maisaka.chat_loop_service import ChatResponse
from src.maisaka.context.messages import ToolResultMessage
from src.maisaka.focus.context import FocusContextEntry
from src.maisaka.focus.group_runtime import FocusGroupRuntime
from src.maisaka.reasoning_engine import CycleRuntimeState, MaisakaReasoningEngine
from src.maisaka.utils.tool_batch import execute_tool_calls


def _response(calls: List[ToolCall], content: str = "查询") -> ChatResponse:
    result = LLMResponseResult.from_portable_output(response=content, tool_calls=calls)
    return ChatResponse(
        output_items=result.output_items,
        request_messages=[],
        selected_history_count=0,
        tool_count=len(calls),
        prompt_tokens=0,
        built_message_count=0,
        completion_tokens=0,
        total_tokens=0,
    )


async def _run_batch(
    executor: str,
    calls: List[ToolCall],
    invoke: Callable[[ToolInvocation, object], Awaitable[ToolExecutionResult]],
    monkeypatch: pytest.MonkeyPatch,
    granted_names: Optional[List[str]] = None,
) -> List[ToolResultMessage]:
    specs = [
        ToolSpec(name=name, provider_name="web_search" if name in {"web_search", "web_fetch"} else "plugin")
        for name in dict.fromkeys(call.func_name for call in calls)
    ]
    registry = SimpleNamespace(list_tools=AsyncMock(return_value=specs), invoke=invoke)
    runtime = SimpleNamespace(
        _tool_registry=registry,
        _chat_history=[],
        session_id="parallel-test",
        chat_stream=SimpleNamespace(is_group_session=True, group_id="group", user_id="", platform="test"),
        expand_message_id_aliases=lambda arguments: arguments,
        is_action_tool_currently_available=lambda name: True,
        _update_stage_status=Mock(),
        _reset_consecutive_wait_count=Mock(),
        _end_planner_continuation=Mock(),
        _enter_stop_state=Mock(),
        log_prefix="[test]",
    )
    engine = MaisakaReasoningEngine(runtime)
    engine._active_logical_turn_id = "turn"
    engine._turn_passive_replyer = False
    engine._record_tool_execution_effects = AsyncMock()
    engine._emit_planner_progress = AsyncMock()
    runtime._reasoning_engine = engine
    runtime.session_name = "并发测试"
    monkeypatch.setattr(global_config.capabilities, "tool_result_condense", False)
    response = _response(calls)

    if executor == "planner":
        _, _, _, monitor = await engine._handle_tool_calls(calls, "查询", SimpleNamespace(), CycleRuntimeState())
        assert [item["tool_call_id"] for item in monitor] == [
            message.tool_call_id for message in runtime._chat_history if isinstance(message, ToolResultMessage)
        ]
        history = runtime._chat_history
    elif executor == "focus":
        group = FocusGroupRuntime("parallel-test")
        group.checkpoint = AsyncMock()
        group._emit_response = AsyncMock()
        group.tools.routes = {spec.name: SimpleNamespace(spec=spec) for spec in specs}

        async def invoke_focus(name, arguments, call_id, reasoning):
            call = ToolCall(call_id=call_id, func_name=name, args=arguments)
            invocation = engine._build_tool_invocation(call, reasoning)
            result = await invoke(invocation, engine._build_tool_execution_context(reasoning))
            return invocation, result, runtime, ToolSpec(name=name)

        group.tools.invoke = invoke_focus
        batch = FocusContextEntry(list(response.raw_messages), {runtime.session_id})
        monitor, _ = await group._execute_tools(response, batch, "turn", group._generation)
        history = batch.messages
        assert [item["tool_call_id"] for item in monitor] == [call.call_id for call in calls]
    else:
        history = []

        async def run_sub_agent(**kwargs):
            if not history:
                history.extend(kwargs["extra_messages"])
                return response
            history[:] = kwargs["extra_messages"]
            return _response([], "结论")

        runtime.run_sub_agent = run_sub_agent
        monkeypatch.setattr(subagent, "emit_subagent_round", AsyncMock())
        result_event = AsyncMock()
        monkeypatch.setattr(subagent, "emit_subagent_tool_result", result_event)
        if granted_names is not None:
            specs = [spec for spec in specs if spec.name in granted_names]
        usage = {}
        outcome = await subagent._run_sub_agent_rounds(
            BuiltinToolRuntimeContext(engine, runtime),
            task_id="subagent-test",
            task="查询",
            granted_specs=specs,
            tool_usage=usage,
            max_rounds=1,
        )
        assert outcome.conclusion == "结论"
        assert sum(usage.values()) == sum(call.func_name in {spec.name for spec in specs} for call in calls)
        assert [call.kwargs["call_id"] for call in result_event.await_args_list] == [call.call_id for call in calls]
        assert runtime._chat_history == []
    return [message for message in history if isinstance(message, ToolResultMessage)]


@pytest.mark.asyncio
@pytest.mark.parametrize("executor", ["subagent", "planner", "focus"])
async def test_parallel_queries_preserve_order_failures_and_serial_barriers(executor, monkeypatch):
    names = ["web_search", "web_fetch", "web_search", "web_fetch", "plugin_edit", "web_search", "web_fetch"]
    calls = [ToolCall(call_id=str(i), func_name=name) for i, name in enumerate(names)]
    active = 0
    peak = 0
    started = []
    finished = []
    ready = asyncio.Event()
    done = [asyncio.Event() for _ in range(3)]

    async def invoke(invocation, context):
        nonlocal active, peak
        index = int(invocation.call_id)
        if invocation.tool_name == "plugin_edit":
            assert active == 0
            assert set(finished) == {0, 1, 2, 3}
        elif index > 4:
            assert 4 in finished
        active += 1
        peak = max(peak, active)
        started.append(index)
        try:
            if index < 3:
                if len(started) == 3:
                    ready.set()
                await ready.wait()
                if index < 2:
                    await done[index + 1].wait()
                done[index].set()
            else:
                await asyncio.sleep(0)
            finished.append(index)
            return ToolExecutionResult(
                tool_name=invocation.tool_name,
                success=index != 1,
                content=f"result-{index}" if index != 1 else "",
                error_message="failure-1" if index == 1 else "",
            )
        finally:
            active -= 1

    history = await asyncio.wait_for(_run_batch(executor, calls, invoke, monkeypatch), timeout=5)
    assert peak == 3
    assert finished[:3] == [2, 1, 0]
    assert started == list(range(len(calls)))
    assert [message.tool_call_id for message in history] == [call.call_id for call in calls]
    for index, message in enumerate(history):
        assert message.tool_name == names[index]
        assert message.success == (index != 1)
        assert message.content == ("failure-1" if index == 1 else f"result-{index}")


@pytest.mark.asyncio
@pytest.mark.parametrize("executor", ["planner", "focus"])
async def test_pause_does_not_start_later_queries(executor, monkeypatch):
    calls = [
        ToolCall(call_id=str(i), func_name=name)
        for i, name in enumerate(["web_search", "web_fetch", "stop", "web_search"])
    ]
    invoked = []

    async def invoke(invocation, context):
        invoked.append(invocation.call_id)
        return ToolExecutionResult(
            tool_name=invocation.tool_name,
            success=True,
            content=invocation.call_id,
            metadata={"pause_execution": invocation.tool_name == "stop"},
        )

    await _run_batch(executor, calls, invoke, monkeypatch)
    assert invoked == ["0", "1", "2"]


@pytest.mark.asyncio
async def test_subagent_only_invokes_granted_queries(monkeypatch):
    calls = [ToolCall(call_id=name, func_name=name) for name in ["web_search", "web_fetch"]]
    invoke = AsyncMock(return_value=ToolExecutionResult(tool_name="web_fetch", success=True, content="page"))
    history = await _run_batch("subagent", calls, invoke, monkeypatch, granted_names=["web_fetch"])
    assert invoke.await_count == 1
    assert invoke.await_args.args[0].tool_name == "web_fetch"
    assert not history[0].success
    assert "没有授权" in history[0].content
    assert history[1].content == "page"


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [True, False])
async def test_interrupted_parallel_batch_cleans_up_all_requests(cancel):
    calls = [ToolCall(call_id=str(i), func_name="web_search") for i in range(4)]
    started = []
    finished = []
    ready = asyncio.Event()
    blocked = asyncio.Event()

    async def invoke(index, call):
        started.append(call.call_id)
        try:
            if len(started) == 3:
                ready.set()
            await ready.wait()
            if not cancel and index == 1:
                raise ValueError("query failed")
            await blocked.wait()
        finally:
            finished.append(call.call_id)

    async def run():
        specs = [ToolSpec(name="web_search", provider_name="web_search")]
        return [result async for result in execute_tool_calls(calls, invoke, specs)]

    task = asyncio.create_task(run())
    await asyncio.wait_for(ready.wait(), timeout=5)
    if cancel:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        with pytest.raises(ValueError, match="query failed"):
            await asyncio.wait_for(task, timeout=5)
    assert started == ["0", "1", "2"]
    assert sorted(finished) == started


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_name", ["plugin", "web_search"])
async def test_query_parallelism_uses_registered_provider_and_alias(provider_name):
    name = "web_search" if provider_name == "plugin" else "web_web_search_web_search"
    calls = [ToolCall(call_id=str(i), func_name=name) for i in range(2)]
    spec = ToolSpec(name=name, provider_name=provider_name, metadata={"registry_original_name": "web_search"})
    active = 0
    peak = 0

    async def invoke(index, call):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        active -= 1
        return call.call_id

    results = [result async for _, _, result in execute_tool_calls(calls, invoke, [spec])]
    assert results == ["0", "1"]
    assert peak == (1 if provider_name == "plugin" else 2)
