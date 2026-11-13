"""按自定义静默时长收齐消息，限制整批及提及消息的等待时间。"""

from typing import Optional
import asyncio

BATCH_LIMIT = 8.0
MENTION_LIMIT = 1.0


class MessageDebouncer:
    """一个运行时一个实例；只管理防抖，不启动后台任务或调用外部接口。"""

    def __init__(self) -> None:
        self._first: Optional[float] = None
        self._last_arrival: Optional[float] = None
        self._deadline: Optional[float] = None
        self._urgent: Optional[float] = None
        self.changed = asyncio.Event()

    @property
    def deadline(self) -> Optional[float]:
        """当前批次的单调时钟截止时间。"""
        return self._deadline

    def observe(
        self,
        *,
        is_pure_emoji: bool,
        at_bot: bool,
        received_at: float,
        wall_time: float,
        now: float,
        wait_seconds: float,
    ) -> str:
        """更新截止时间并返回本次规则说明；预处理耗时也占用 8 秒/1 秒上限。"""
        arrival = now - max(0.0, wall_time - received_at)
        if self._last_arrival is not None:
            arrival = max(arrival, self._last_arrival)
        self._last_arrival = arrival
        new_batch = self._first is None
        if new_batch:
            self._first = arrival
        if at_bot:
            urgent = now - max(0.0, wall_time - received_at) + MENTION_LIMIT
            self._urgent = min(self._urgent, urgent) if self._urgent is not None else urgent
        # 已到期但因模型/工具忙碌尚未消费的批次，不允许被新消息重新延长。
        # 这些消息仍进入原有上下文缓存，一起消费，不为补偿模型忙碌再排一遍队。
        if self._deadline is None or self._deadline > now:
            reasons = [f"{'开批' if new_batch else '续发'}等待 {wait_seconds:g} 秒"]
            limit = self._first + BATCH_LIMIT
            if self._urgent is not None:
                limit = min(limit, self._urgent)
            candidate = arrival + wait_seconds
            # 纯表情包仍可把截止时间提前，但不能在已有批次上继续续长。
            if is_pure_emoji and not new_batch:
                reasons.append("纯表情包不延长等待")
                candidate = min(candidate, self._deadline)
            if candidate > self._first + BATCH_LIMIT:
                reasons.append("受整批 8 秒上限限制")
            if self._urgent is not None and candidate > self._urgent:
                reasons.append("受@或提及 1 秒上限限制")
            self._deadline = min(candidate, limit)
            reason = "；".join(reasons)
        else:
            reason = "批次已到期，不再延长等待"
        self.changed.set()
        return reason

    def consume(self) -> None:
        """本批消息已收走，清除当前批次的计时状态。"""
        self._first = self._last_arrival = self._deadline = self._urgent = None
        self.changed.set()
