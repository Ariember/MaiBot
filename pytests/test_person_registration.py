from contextlib import contextmanager

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, create_engine, select

import json
import pytest


def test_group_registration_reports_success_after_single_write(monkeypatch, tmp_path):
    monkeypatch.setenv("MAIBOT_INSTANCE_DIR", str(tmp_path))
    from src.common.database.database_model import PersonInfo
    from src.person_info import person_info

    engine = create_engine("sqlite://")
    PersonInfo.__table__.create(engine)
    write_transactions = 0

    @contextmanager
    def db_session():
        nonlocal write_transactions
        with Session(engine) as session, session.begin():
            yield session
            if session.new or session.dirty:
                write_transactions += 1

    monkeypatch.setattr(person_info, "get_db_session", db_session)
    messages = []
    monkeypatch.setattr(person_info.logger, "info", messages.append)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TRIGGER reject_person BEFORE INSERT ON person_info "
            "BEGIN SELECT RAISE(ABORT, 'registration failed'); END"
        )
    with pytest.raises(IntegrityError, match="registration failed"):
        person_info.Person.register_person("qq", "123", "昵称", "group", "群名片")
    assert not messages
    with Session(engine) as session:
        assert session.exec(select(PersonInfo)).first() is None

    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TRIGGER reject_person")
    write_transactions = 0
    person = person_info.Person.register_person("qq", "123", "昵称", "group", "群名片")
    assert write_transactions == 1
    assert any("成功注册新用户" in message for message in messages)
    with Session(engine) as session:
        record = session.exec(select(PersonInfo)).one()
        assert record.person_id == person.person_id
        assert json.loads(record.group_cardname) == [{"group_id": "group", "group_cardname": "群名片"}]
    engine.dispose()
