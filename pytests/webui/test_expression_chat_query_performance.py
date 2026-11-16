from contextlib import contextmanager
from datetime import datetime, timedelta

from sqlalchemy import event
from sqlmodel import Session, create_engine

import pytest

from src.common.database.database_model import ChatSession, Expression, Messages
from src.webui.routers import expression


@pytest.fixture
def storage(monkeypatch):
    engine = create_engine("sqlite://")
    for model in (ChatSession, Expression, Messages):
        model.__table__.create(engine)

    @contextmanager
    def db_session():
        with Session(engine) as session:
            yield session

    statements = []

    def record_query(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", record_query)
    monkeypatch.setattr(expression, "get_db_session", db_session)
    monkeypatch.setattr(expression, "get_configured_platform_accounts", lambda: {("qq", "bot")})
    monkeypatch.setattr(expression, "get_chat_name", lambda chat_id, _session: chat_id)
    monkeypatch.setattr(
        expression.ExpressionConfigUtils, "get_expression_config_for_chat", lambda _chat_id: (True, True)
    )
    yield engine, statements
    engine.dispose()


@pytest.mark.parametrize("count", [1, 100])
@pytest.mark.parametrize("include_legacy", [False, True])
def test_chat_list_batches_session_queries(storage, count, include_legacy):
    engine, statements = storage
    with Session(engine) as session:
        for index in range(count):
            chat_id = f"chat-{index:03d}"
            session.add(ChatSession(session_id=chat_id, platform="qq", account_id="bot", user_id=str(index)))
            session.add(Expression(session_id=chat_id, situation="情景", style="表达", content_list="[]"))
        session.commit()
    statements.clear()

    result = expression.get_chat_list(include_legacy=include_legacy)

    assert result.success
    assert [item.chat_id for item in result.data] == [f"chat-{index:03d}" for index in range(count)]
    assert all(item.expression_count == 1 for item in result.data)
    assert len(statements) == (4 if include_legacy else 5)
    assert sum("FROM chat_sessions" in statement for statement in statements) == (1 if include_legacy else 2)


@pytest.mark.parametrize("include_legacy", [False, True])
def test_chat_list_preserves_visibility_metadata_counts_and_order(storage, monkeypatch, include_legacy):
    engine, _statements = storage
    records = [
        ChatSession(session_id="group", platform="qq", account_id="bot", group_id="10"),
        ChatSession(session_id="private-a", platform="qq", account_id="bot", user_id="11"),
        ChatSession(session_id="private-b", platform="qq", account_id="bot", user_id="12"),
        ChatSession(session_id="no-message", platform="qq", account_id="bot", user_id="13"),
        ChatSession(session_id="legacy", platform="qq", user_id="14"),
        ChatSession(session_id="other", platform="qq", account_id="other-bot", group_id="15"),
        ChatSession(session_id="unused", platform="qq", account_id="bot", user_id="16"),
    ]
    chat_ids = [record.session_id for record in records if record.session_id != "unused"] + ["missing"]
    names = {chat_id: chat_id for chat_id in chat_ids}
    names.update({"private-a": "同名私聊", "private-b": "同名私聊"})
    monkeypatch.setattr(expression, "get_chat_name", lambda chat_id, _session: names[chat_id])
    monkeypatch.setattr(
        expression.ExpressionConfigUtils,
        "get_expression_config_for_chat",
        lambda chat_id: (chat_id != "group", chat_id != "private-a"),
    )
    timestamp = datetime(2026, 1, 1)
    with Session(engine, expire_on_commit=False) as session:
        session.add_all(records)
        for chat_id in [*chat_ids, "group", None]:
            session.add(Expression(session_id=chat_id, situation="情景", style="表达", content_list="[]"))
        for index, chat_id in enumerate(["legacy", "other", "missing", "private-b", "private-a", "group", "group"]):
            offset = 3 if chat_id.startswith("private-") else index
            session.add(
                Messages(
                    message_id=f"message-{index}",
                    timestamp=timestamp + timedelta(hours=offset),
                    platform="qq",
                    user_id="sender",
                    user_nickname="发言者",
                    session_id=chat_id,
                    raw_content=b"",
                )
            )
        session.commit()

    result = expression.get_chat_list(include_legacy=include_legacy)

    expected_ids = ["group", "private-a", "private-b"]
    if include_legacy:
        expected_ids += ["missing", "other", "legacy"]
    expected_ids.append("no-message")
    assert result.success
    assert [item.chat_id for item in result.data] == expected_ids
    records_by_id = {record.session_id: record for record in records}
    for item in result.data:
        record = records_by_id.get(item.chat_id)
        assert item.model_dump() == {
            "chat_id": item.chat_id,
            "chat_name": names[item.chat_id],
            "platform": record.platform if record else None,
            "account_id": record.account_id if record else None,
            "target_id": (record.group_id or record.user_id) if record else None,
            "is_group": bool(record and record.group_id),
            "is_legacy": item.chat_id in {"legacy", "missing"},
            "is_other_account": item.chat_id == "other",
            "use_expression": item.chat_id != "group",
            "enable_learning": item.chat_id != "private-a",
            "expression_count": 2 if item.chat_id == "group" else 1,
        }


@pytest.mark.parametrize("include_legacy", [False, True])
def test_empty_chat_list(storage, include_legacy):
    result = expression.get_chat_list(include_legacy=include_legacy)
    assert result.model_dump() == {"success": True, "data": []}
