from datetime import datetime
from threading import get_ident

import pytest

from src.chat.message_receive.message import SessionMessage
from src.common.data_models.mai_message_data_model import MessageInfo, UserInfo
from src.common.data_models.message_component_data_model import MessageSequence, TextComponent
from src.plugin_runtime.capabilities.data import RuntimeDataCapabilityMixin
from src.services import message_service


@pytest.fixture
def message() -> SessionMessage:
    message = SessionMessage(message_id="message-1", timestamp=datetime.now(), platform="test")
    message.message_info = MessageInfo(user_info=UserInfo(user_id="user-1", user_nickname="测试用户"))
    message.raw_message = MessageSequence([TextComponent("你好")])
    message.session_id = "chat-1"
    message.processed_plain_text = "你好"
    return message


@pytest.mark.asyncio
@pytest.mark.parametrize("from_query", [False, True])
async def test_build_readable_preserves_output_off_loop(monkeypatch, message, from_query) -> None:
    loop_thread = get_ident()
    calls = []

    capability = RuntimeDataCapabilityMixin()
    serialized_messages = capability._serialize_messages([message], include_binary_data=False)
    deserialize = capability._deserialize_messages
    build_readable = message_service.build_readable_messages

    def query(**kwargs):
        assert get_ident() != loop_thread
        assert kwargs == {"chat_id": "chat-1", "start_time": 0.0, "end_time": 0.0, "limit": 0}
        calls.append("query")
        return [message]

    def deserialize_off_loop(messages):
        assert get_ident() != loop_thread
        calls.append("deserialize")
        return deserialize(messages)

    def build_off_loop(**kwargs):
        assert get_ident() != loop_thread
        calls.append("build")
        return build_readable(**kwargs)

    monkeypatch.setattr(message_service, "get_messages_by_time_in_chat", query)
    monkeypatch.setattr(capability, "_deserialize_messages", deserialize_off_loop)
    monkeypatch.setattr(message_service, "build_readable_messages", build_off_loop)
    result = await capability._cap_message_build_readable(
        plugin_id="test.plugin",
        capability="message.build_readable",
        args={
            **({"chat_id": "chat-1"} if from_query else {"messages": serialized_messages}),
            "replace_bot_name": False,
            "timestamp_mode": None,
        },
    )

    assert result == {"success": True, "text": "测试用户说：你好"}
    assert calls == ["query" if from_query else "deserialize", "build"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("handler", "service_name", "args", "expected_query"),
    [
        (
            RuntimeDataCapabilityMixin._cap_message_get_by_time,
            "get_messages_by_time",
            {"start_time": "10", "end_time": "20", "limit": 2, "limit_mode": "earliest", "filter_mai": True},
            {"start_time": 10.0, "end_time": 20.0, "limit": 2, "limit_mode": "earliest", "filter_mai": True},
        ),
        (
            RuntimeDataCapabilityMixin._cap_message_get_by_time_in_chat,
            "get_messages_by_time_in_chat",
            {"chat_id": "chat-1", "filter_command": True},
            {
                "chat_id": "chat-1",
                "start_time": 0.0,
                "end_time": 0.0,
                "limit": 0,
                "limit_mode": "latest",
                "filter_mai": False,
                "filter_command": True,
            },
        ),
        (
            RuntimeDataCapabilityMixin._cap_message_get_recent,
            "get_messages_by_time_in_chat",
            {"chat_id": "chat-1", "hours": "2"},
            {
                "chat_id": "chat-1",
                "start_time": 2800.0,
                "end_time": 10000.0,
                "limit": 100,
                "limit_mode": "latest",
                "filter_mai": False,
            },
        ),
    ],
)
@pytest.mark.parametrize("include_binary_data", [False, True])
async def test_message_queries_and_serialization_run_off_loop(
    monkeypatch, message, handler, service_name, args, expected_query, include_binary_data
) -> None:
    loop_thread = get_ident()
    capability = RuntimeDataCapabilityMixin()
    serialize = capability._serialize_messages
    expected = serialize([message], include_binary_data=include_binary_data)
    calls = []

    def query(**kwargs):
        assert get_ident() != loop_thread
        assert kwargs == expected_query
        calls.append("query")
        return [message]

    def serialize_off_loop(messages, **kwargs):
        assert get_ident() != loop_thread
        assert kwargs == {"include_binary_data": include_binary_data}
        calls.append("serialize")
        return serialize(messages, **kwargs)

    monkeypatch.setattr("src.plugin_runtime.capabilities.data.time.time", lambda: 10000.0)
    monkeypatch.setattr(message_service, service_name, query)
    monkeypatch.setattr(capability, "_serialize_messages", serialize_off_loop)
    result = await handler(
        capability, "test.plugin", "message.query", {**args, "include_binary_data": include_binary_data}
    )

    assert result == {"success": True, "messages": expected}
    assert calls == ["query", "serialize"]


@pytest.mark.asyncio
async def test_message_count_preserves_since_and_runs_off_loop(monkeypatch) -> None:
    loop_thread = get_ident()

    def count(**kwargs):
        assert get_ident() != loop_thread
        assert kwargs == {"chat_id": "chat-1", "start_time": 10.0, "end_time": 20.0}
        return 3

    monkeypatch.setattr(message_service, "count_new_messages", count)
    result = await RuntimeDataCapabilityMixin()._cap_message_count_new(
        "test.plugin",
        "message.count_new",
        {"chat_id": "chat-1", "since": "10", "start_time": 1.0, "end_time": 20.0},
    )

    assert result == {"success": True, "count": 3}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("handler", "service_name"),
    [
        (RuntimeDataCapabilityMixin._cap_message_get_by_time, "get_messages_by_time"),
        (RuntimeDataCapabilityMixin._cap_message_get_by_time_in_chat, "get_messages_by_time_in_chat"),
        (RuntimeDataCapabilityMixin._cap_message_get_recent, "get_messages_by_time_in_chat"),
        (RuntimeDataCapabilityMixin._cap_message_count_new, "count_new_messages"),
        (RuntimeDataCapabilityMixin._cap_message_build_readable, "get_messages_by_time_in_chat"),
    ],
)
async def test_message_query_errors_keep_response(monkeypatch, handler, service_name) -> None:
    def fail(**kwargs):
        raise RuntimeError("query failed")

    monkeypatch.setattr(message_service, service_name, fail)
    result = await handler(RuntimeDataCapabilityMixin(), "test.plugin", "message.query", {"chat_id": "chat-1"})

    assert result == {"success": False, "error": "query failed"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("messages", "error"),
    [("invalid", "messages 必须是消息字典列表"), (["invalid"], "messages[0] 必须是消息字典")],
)
async def test_build_readable_keeps_message_validation(messages, error) -> None:
    result = await RuntimeDataCapabilityMixin()._cap_message_build_readable(
        "test.plugin", "message.build_readable", {"messages": messages}
    )

    assert result == {"success": False, "error": error}
