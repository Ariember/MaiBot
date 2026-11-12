from datetime import datetime

from sqlalchemy import create_engine, func
from sqlmodel import select

import pytest

from src.common.database import database
from src.common.database.database_model import Messages
from src.common.message_repository import message_time_expression


def test_runtime_index_preserves_statistics_time_and_avoids_full_scan(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'statistics.db'}")
    monkeypatch.setattr(database, "engine", engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE jargons (id INTEGER PRIMARY KEY, is_jargon INTEGER, is_global INTEGER, "
            "is_complete INTEGER, count INTEGER)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE mai_messages (id INTEGER PRIMARY KEY, session_id TEXT, timestamp DATETIME, "
            "received_at DATETIME, reply_to TEXT)"
        )
        connection.exec_driver_sql("CREATE TABLE tool_records (tool_name TEXT, timestamp DATETIME)")
        connection.exec_driver_sql(
            "INSERT INTO tool_records VALUES (?, ?)",
            [("reply", "2026-10-26"), ("reply", "2026-10-27"), ("stop", "2026-10-27")],
        )
        # 包含历史/出站消息、接收时间跨过边界以及上游时间在边界后但接收时间在边界前的消息。
        connection.exec_driver_sql(
            "INSERT INTO mai_messages (id, session_id, timestamp, received_at) VALUES (?, 'chat', ?, ?)",
            [
                (1, "2026-10-26 12:00:00.000000", None),
                (2, "2026-10-27 12:00:00.000000", None),
                (3, "2026-10-26 12:00:00.000000", "2026-10-27 12:00:00.000001"),
                (4, "2026-10-27 13:00:00.000000", "2026-10-26 12:00:00.000000"),
            ],
        )

    expression = message_time_expression("statistics_time")
    query = select(Messages.id).where(expression >= datetime(2026, 10, 27, 12))
    sql = str(query.compile(engine, compile_kwargs={"literal_binds": True}))
    with engine.connect() as connection:
        expected = connection.execute(query).scalars().all()
        assert expected == [2, 3]
        assert "SCAN mai_messages" in str(connection.exec_driver_sql("EXPLAIN QUERY PLAN " + sql).all())

    # 启动时能为已有库补建，并可重复执行；新库也走相同初始化入口。
    database.ensure_runtime_performance_indexes()
    database.ensure_runtime_performance_indexes()
    with engine.connect() as connection:
        assert sorted(connection.execute(query).scalars().all()) == expected
        plan = str(connection.exec_driver_sql("EXPLAIN QUERY PLAN " + sql).all())
        assert "SEARCH mai_messages" in plan
        assert "ix_mai_messages_statistics_time" in plan
        assert "SCAN mai_messages" not in plan
        earliest = select(func.min(expression))
        earliest_sql = str(earliest.compile(engine, compile_kwargs={"literal_binds": True}))
        assert "ix_mai_messages_statistics_time" in str(
            connection.exec_driver_sql("EXPLAIN QUERY PLAN " + earliest_sql).all()
        )
        reply_query = "SELECT COUNT(*) FROM tool_records WHERE tool_name = 'reply' AND timestamp >= '2026-10-27'"
        assert connection.exec_driver_sql(reply_query).scalar_one() == 1
        reply_plan = str(connection.exec_driver_sql("EXPLAIN QUERY PLAN " + reply_query).all())
        assert "ix_tool_records_tool_name_timestamp" in reply_plan
        assert "tool_name=? AND timestamp>?" in reply_plan
    engine.dispose()


@pytest.mark.parametrize("existing_rows", [True, False])
def test_reply_target_index_preserves_lookup_and_updates(tmp_path, monkeypatch, existing_rows):
    engine = create_engine(f"sqlite:///{tmp_path / 'reply_targets.db'}")
    monkeypatch.setattr(database, "engine", engine)
    records = [
        Messages(
            id=record_id,
            message_id=f"message-{record_id}",
            timestamp=datetime(2026, 11, 12),
            platform="test",
            user_id="user",
            user_nickname="User",
            session_id="chat",
            raw_content=b"",
            reply_to=reply_to,
        ).model_dump()
        for record_id, reply_to in [(1, None), (2, ""), (3, "old-id"), (4, "old-id"), (5, "other-id")]
    ]
    with engine.begin() as connection:
        Messages.__table__.create(connection)
        connection.exec_driver_sql(
            "CREATE TABLE jargons (id INTEGER PRIMARY KEY, is_jargon INTEGER, is_global INTEGER, "
            "is_complete INTEGER, count INTEGER)"
        )
        connection.exec_driver_sql("CREATE TABLE tool_records (tool_name TEXT, timestamp DATETIME)")
        if existing_rows:
            connection.execute(Messages.__table__.insert(), records)

        query = select(Messages).filter_by(reply_to="old-id")
        sql = str(query.compile(engine, compile_kwargs={"literal_binds": True}))
        assert "SCAN mai_messages" in str(connection.exec_driver_sql("EXPLAIN QUERY PLAN " + sql).all())

    database.ensure_runtime_performance_indexes()
    database.ensure_runtime_performance_indexes()
    with engine.begin() as connection:
        if not existing_rows:
            connection.execute(Messages.__table__.insert(), records)
        for reply_to, expected in [(None, [1]), ("", [2]), ("old-id", [3, 4]), ("missing", [])]:
            query = select(Messages).filter_by(reply_to=reply_to)
            assert [row.id for row in connection.execute(query)] == expected
            if reply_to is not None:
                sql = str(query.compile(engine, compile_kwargs={"literal_binds": True}))
                plan = str(connection.exec_driver_sql("EXPLAIN QUERY PLAN " + sql).all())
                assert "SEARCH mai_messages USING INDEX ix_mai_messages_reply_to" in plan
                assert "SCAN mai_messages" not in plan

        connection.execute(
            Messages.__table__.update().where(Messages.reply_to == "old-id").values(reply_to="new-id")
        )
        assert connection.execute(select(Messages).filter_by(reply_to="old-id")).all() == []
        assert [row.id for row in connection.execute(select(Messages).filter_by(reply_to="new-id"))] == [3, 4]
        assert connection.execute(select(Messages.reply_to).where(Messages.id == 5)).scalar_one() == "other-id"
    engine.dispose()
