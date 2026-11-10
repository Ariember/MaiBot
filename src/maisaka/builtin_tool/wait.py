"""wait 内置工具。"""

from datetime import datetime
from math import ceil
from typing import Any, Dict, Optional

from src.config.config import global_config
from src.core.tooling import ToolExecutionContext, ToolExecutionResult, ToolInvocation, ToolSpec

from .context import BuiltinToolRuntimeContext


def get_tool_spec() -> ToolSpec:
    """获取 wait 工具声明。"""

    return ToolSpec(
        name="wait",
        description="等待指定秒数或等到绝对时间后再次判断；seconds 与 until 必须二选一。",
        parameters_schema={
            "type": "object",
            "properties": {
                "seconds": {
                    "type": "integer",
                    "minimum": 0,
                    "description": "等待秒数。",
                },
                "until": {
                    "type": "string",
                    "description": "ISO 8601 绝对时间，建议携带时区偏移，如 2026-11-10T20:30:00+08:00；无时区按服务器本地时间。",
                },
            },
            "oneOf": [
                {"required": ["seconds"], "not": {"required": ["until"]}},
                {"required": ["until"], "not": {"required": ["seconds"]}},
            ],
        },
        provider_name="maisaka_builtin",
        provider_type="builtin",
    )


def resolve_wait_seconds(arguments: Dict[str, Any]) -> int:
    """将相对秒数或绝对时间转为普通聊天和 Focus 共用的等待秒数。"""

    if ("seconds" in arguments) == ("until" in arguments):
        raise ValueError("wait 的 seconds 和 until 必须二选一")
    if "until" in arguments:
        until = arguments["until"]
        if not isinstance(until, str):
            raise ValueError("wait.until 必须是 ISO 8601 时间字符串")
        try:
            deadline = datetime.fromisoformat(until)
        except ValueError as exc:
            raise ValueError("wait.until 必须是有效的 ISO 8601 时间字符串") from exc
        return max(0, ceil((deadline - datetime.now(deadline.tzinfo)).total_seconds()))
    seconds = arguments["seconds"]
    if isinstance(seconds, bool) or not isinstance(seconds, int) or seconds < 0:
        raise ValueError("wait.seconds 必须是非负整数")
    return seconds


async def handle_tool(
    tool_ctx: BuiltinToolRuntimeContext,
    invocation: ToolInvocation,
    context: Optional[ToolExecutionContext] = None,
) -> ToolExecutionResult:
    """执行 wait 内置工具。"""

    del context
    wait_seconds = resolve_wait_seconds(invocation.arguments)
    current_count = tool_ctx.runtime._enter_counted_wait_state(
        seconds=wait_seconds,
        tool_call_id=invocation.call_id,
        logical_turn_id=tool_ctx.engine.active_logical_turn_id,
    )
    wait_detail = (
        f"当前对话循环进入等待状态，最多等待 {wait_seconds} 秒；新消息可提前结束等待并继续思考。"
        if global_config.chat.reply_timing.planner_message_steering
        else f"当前对话循环进入等待状态，将固定等待 {wait_seconds} 秒；期间收到的新消息不会提前打断本次等待。"
    )
    return tool_ctx.build_success_result(
        invocation.tool_name,
        f"{wait_detail}连续 wait 次数：{current_count}。",
        metadata={
            "pause_execution": True,
            "consecutive_wait_count": current_count,
        },
    )
