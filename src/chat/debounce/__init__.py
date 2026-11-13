"""按自定义静默时长收齐会话中的连发消息，减少重复判断。"""

from .controller import MessageDebouncer

__all__ = ["MessageDebouncer"]
