"""普通聊天与 Focus 共用等待时间的解析和校验。"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.maisaka.builtin_tool import wait as wait_tool
from src.maisaka.builtin_tool.context import BuiltinToolRuntimeContext
from src.maisaka.focus.group_runtime import FocusGroupRuntime


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("until", "expected"),
    [
        ("2026-11-10T20:01:00+08:00", 60),
        ("2026-11-10T12:01:00Z", 60),
        ("2026-11-10T12:01:00", 60),
        ("2026-11-10T12:00:00.5+00:00", 1),
        ("2026-11-10T11:59:00Z", 0),
    ],
)
async def test_absolute_wait_preserves_turn_and_pause_metadata(monkeypatch, until: str, expected: int) -> None:
    now = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
    clock = Mock(wraps=datetime)
    clock.now.side_effect = lambda tz=None: now.astimezone(tz) if tz else now.replace(tzinfo=None)
    monkeypatch.setattr(wait_tool, "datetime", clock)
    runtime = SimpleNamespace(_enter_counted_wait_state=Mock(return_value=2))
    context = BuiltinToolRuntimeContext(SimpleNamespace(active_logical_turn_id="turn"), runtime)
    invocation = SimpleNamespace(arguments={"until": until}, call_id="wait-call", tool_name="wait")

    result = await wait_tool.handle_tool(context, invocation)

    runtime._enter_counted_wait_state.assert_called_once_with(
        seconds=expected,
        tool_call_id="wait-call",
        logical_turn_id="turn",
    )
    assert result.success
    assert result.metadata == {"pause_execution": True, "consecutive_wait_count": 2}


@pytest.mark.parametrize("seconds", [0, 30])
def test_relative_wait_preserves_seconds(seconds: int) -> None:
    assert wait_tool.resolve_wait_seconds({"seconds": seconds}) == seconds


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"seconds": 1, "until": "2026-11-10T20:30:00+08:00"},
        {"seconds": True},
        {"seconds": -1},
        {"seconds": 1.5},
        {"seconds": "30"},
        {"until": None},
        {"until": 123},
        {"until": "不是时间"},
    ],
)
async def test_invalid_wait_does_not_enter_normal_or_focus_wait(arguments) -> None:
    runtime = SimpleNamespace(_enter_counted_wait_state=Mock())
    context = BuiltinToolRuntimeContext(SimpleNamespace(active_logical_turn_id="turn"), runtime)
    invocation = SimpleNamespace(arguments=arguments, call_id="wait-call", tool_name="wait")
    with pytest.raises(ValueError, match="wait"):
        await wait_tool.handle_tool(context, invocation)
    runtime._enter_counted_wait_state.assert_not_called()

    group = SimpleNamespace(_consecutive_waits=0, _wait_until=None)
    result = FocusGroupRuntime.execute_control(group, "wait", arguments, "chat")
    assert not result.success
    assert "wait" in result.error_message
    assert group._consecutive_waits == 0
    assert group._wait_until is None
