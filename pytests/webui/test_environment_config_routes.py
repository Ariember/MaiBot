from unittest.mock import AsyncMock, Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
import pytest

from src.webui.routers import config as config_routes


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(config_routes.router)
    app.dependency_overrides[config_routes.require_auth] = lambda: "test-token"
    return TestClient(app)


@pytest.fixture
def upstream(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    client = AsyncMock()
    client.__aenter__.return_value = client
    monkeypatch.setattr(config_routes.httpx, "AsyncClient", Mock(return_value=client))
    monkeypatch.setattr(config_routes, "get_shared_ssl_context_async", AsyncMock(return_value=None))
    return client


def test_timezones_are_sorted_and_include_utc(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config_routes, "available_timezones", lambda: {"Asia/Tokyo", "Asia/Shanghai"})
    response = client.get("/config/environment/timezones")
    assert response.status_code == 200
    assert response.json() == {"timezones": ["Asia/Shanghai", "Asia/Tokyo", "UTC"]}


def test_city_search_returns_selection_fields(client: TestClient, upstream: AsyncMock) -> None:
    city = {
        "id": 1796236,
        "name": "上海",
        "admin1": "上海市",
        "admin2": "上海市",
        "country": "中国",
        "timezone": "Asia/Shanghai",
        "latitude": 31.22222,
        "longitude": 121.45806,
    }
    upstream.get.return_value = httpx.Response(
        200,
        json={"results": [{**city, "population": 24874500}]},
        request=httpx.Request("GET", "https://geocoding-api.open-meteo.com/v1/search"),
    )
    response = client.get("/config/environment/cities", params={"name": " 上海 "})
    assert response.status_code == 200
    assert response.json() == {"cities": [city]}
    upstream.get.assert_awaited_once_with(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": "上海", "count": 10, "language": "zh", "format": "json"},
    )


def test_city_search_without_matches_returns_empty_list(client: TestClient, upstream: AsyncMock) -> None:
    upstream.get.return_value = httpx.Response(
        200, json={}, request=httpx.Request("GET", "https://geocoding-api.open-meteo.com/v1/search")
    )
    assert client.get("/config/environment/cities", params={"name": "不存在的城市"}).json() == {"cities": []}


@pytest.mark.parametrize("name", ["a", "a" * 101, "  "])
def test_city_search_rejects_invalid_name(client: TestClient, upstream: AsyncMock, name: str) -> None:
    assert client.get("/config/environment/cities", params={"name": name}).status_code == 422
    upstream.get.assert_not_awaited()


@pytest.mark.parametrize(
    "result",
    [
        httpx.TimeoutException("private-city-query"),
        httpx.Response(503, text="private-city-query"),
        httpx.Response(200, text="not-json"),
        httpx.Response(200, json={"error": True, "reason": "private-city-query"}),
        httpx.Response(200, json={"results": {}}),
        httpx.Response(200, json={"results": [{"id": 1}]}),
    ],
)
def test_city_search_upstream_failures_are_reported_without_query(
    client: TestClient, upstream: AsyncMock, result: object
) -> None:
    if isinstance(result, Exception):
        upstream.get.side_effect = result
    else:
        result.request = httpx.Request("GET", "https://geocoding-api.open-meteo.com/v1/search?name=private-city-query")
        upstream.get.return_value = result
    response = client.get("/config/environment/cities", params={"name": "private-city-query"})
    assert response.status_code == 502
    assert response.json() == {"detail": "城市查询服务暂时不可用，请稍后重试"}


def test_environment_section_schema_is_registered(client: TestClient) -> None:
    response = client.get("/config/schema/section/environment")
    assert response.status_code == 200
    assert {field["name"] for field in response.json()["schema"]["fields"]} >= {"timezone", "city"}
