"""判断当前时间是否处于允许工作时段。"""


class RestGate:
    @staticmethod
    def in_work_window(start: str, end: str, current: str) -> bool:
        """开始时刻包含、结束时刻不包含；相同表示全天，支持跨午夜。"""
        if start == end:
            return True
        return start <= current < end if start < end else current >= start or current < end
