"""按调用顺序执行工具，仅对连续的独立联网查询做有限并发。"""

from typing import AsyncIterator, Awaitable, Callable, Iterable, List, Tuple, TypeVar

import asyncio

from src.core.tooling import ToolSpec
from src.llm_models.payload_content.tool_option import ToolCall

PARALLEL_QUERY_TOOL_NAMES = frozenset({"web_search", "web_fetch"})
MAX_PARALLEL_QUERY_CALLS = 3

T = TypeVar("T")


async def execute_tool_calls(
    tool_calls: List[ToolCall],
    invoke: Callable[[int, ToolCall], Awaitable[T]],
    tool_specs: Iterable[ToolSpec],
) -> AsyncIterator[Tuple[int, ToolCall, T]]:
    """连续查询每批最多执行三个，结果按原顺序返回；其他工具保持串行。"""
    parallel_query_names = {
        spec.name
        for spec in tool_specs
        if spec.provider_name == "web_search"
        and spec.metadata.get("registry_original_name", spec.name) in PARALLEL_QUERY_TOOL_NAMES
    }
    index = 0
    while index < len(tool_calls):
        end = index + 1
        if tool_calls[index].func_name in parallel_query_names:
            while (
                end < len(tool_calls)
                and end - index < MAX_PARALLEL_QUERY_CALLS
                and tool_calls[end].func_name in parallel_query_names
            ):
                end += 1

        if end == index + 1:
            results = [await invoke(index + 1, tool_calls[index])]
        else:
            tasks = [asyncio.create_task(invoke(i + 1, tool_calls[i])) for i in range(index, end)]
            try:
                results = await asyncio.gather(*tasks)
            finally:
                # 失败或取消时收回同批请求，不能让它们继续在后台运行。
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

        for offset, result in enumerate(results):
            yield index + offset + 1, tool_calls[index + offset], result
        index = end
