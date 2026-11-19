import json

from src.common.logger import file_formatter, get_logger


def test_bound_logger_formats_positional_arguments(caplog):
    get_logger("test_positional_logging").warning("请求 %s 重试 %d 次", "chat", 2)

    event = json.loads(file_formatter.format(caplog.records[-1]))
    assert event["event"] == "请求 chat 重试 2 次"
    assert "positional_args" not in event
