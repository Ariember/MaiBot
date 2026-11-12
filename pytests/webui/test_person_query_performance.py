from contextlib import contextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine

import pytest

from src.common.database.database_model import PersonInfo
from src.webui.dependencies import require_auth
from src.webui.routers import person


@pytest.fixture
def storage(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    PersonInfo.__table__.create(engine)

    @contextmanager
    def db_session():
        with Session(engine) as session:
            yield session

    monkeypatch.setattr(person, "get_db_session", db_session)
    app = FastAPI()
    app.include_router(person.router)
    app.dependency_overrides[require_auth] = lambda: True
    with TestClient(app) as client:
        yield engine, client
    engine.dispose()


@pytest.fixture
def people(storage):
    engine, client = storage
    timestamp = datetime(2026, 1, 1)
    with Session(engine) as session:
        for index, (platform, known, name, nickname, user_id) in enumerate(
            [
                ("qq", True, "小明", "昵称一", "1001"),
                ("qq", False, None, "小明", "1002"),
                ("discord", True, "小明", "昵称三", "1001"),
                ("qq", True, "小明", "昵称四", "1003"),
                ("", False, None, "昵称五", "1004"),
            ]
        ):
            session.add(
                PersonInfo(
                    person_id=f"person-{index}",
                    platform=platform,
                    is_known=known,
                    person_name=name,
                    user_nickname=nickname,
                    user_id=user_id,
                    last_known_time=timestamp + timedelta(days=index) if index != 4 else None,
                )
            )
        session.commit()
    return client


@pytest.mark.parametrize(
    ("filters", "expected_ids"),
    [
        ({}, ["person-3", "person-2", "person-1", "person-0", "person-4"]),
        ({"search": "小明"}, ["person-3", "person-2", "person-1", "person-0"]),
        ({"search": "1001"}, ["person-2", "person-0"]),
        ({"is_known": False}, ["person-1", "person-4"]),
        ({"is_known": True}, ["person-3", "person-2", "person-0"]),
        ({"platform": "qq"}, ["person-3", "person-1", "person-0"]),
        ({"user_id": "1001"}, ["person-2", "person-0"]),
        ({"search": "小明", "is_known": True, "platform": "qq"}, ["person-3", "person-0"]),
        ({"user_id": "1001", "platform": "qq"}, ["person-0"]),
        ({"search": "没有匹配"}, []),
    ],
)
def test_person_list_count_matches_filters_and_all_pages(people, filters, expected_ids):
    actual_ids = []
    for page in range(1, len(expected_ids) + 2):
        response = people.get("/person/list", params={**filters, "page_size": 1, "page": page})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["total"] == len(expected_ids)
        assert result["page"] == page
        assert result["page_size"] == 1
        actual_ids.extend(item["person_id"] for item in result["data"])
    assert actual_ids == expected_ids


def test_person_stats_counts_unnamed_people_and_excludes_empty_platform(people):
    response = people.get("/person/stats/summary")
    assert response.status_code == 200, response.text
    assert response.json() == {
        "success": True,
        "data": {"total": 5, "known": 3, "unknown": 2, "platforms": {"qq": 3, "discord": 1}},
    }


def test_empty_person_queries(storage):
    _, client = storage
    response = client.get("/person/stats/summary")
    assert response.status_code == 200, response.text
    assert response.json()["data"] == {"total": 0, "known": 0, "unknown": 0, "platforms": {}}
    response = client.get("/person/list")
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 0
    assert response.json()["data"] == []
