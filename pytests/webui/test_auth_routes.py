from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.webui.core import auth, security
from src.webui.routes import router


@pytest.fixture
def auth_client(monkeypatch, tmp_path):
    token_manager = security.TokenManager(tmp_path / "webui.json")
    monkeypatch.setattr(security, "_token_manager_instance", token_manager)
    monkeypatch.setattr(auth.global_config.webui, "secure_cookie", False)
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        client.cookies.set(
            auth.COOKIE_NAME, token_manager.encode_cookie_token(token_manager.get_token()), domain="testserver.local"
        )
        yield client, token_manager


def test_first_password_keeps_current_browser_signed_in(auth_client):
    client, token_manager = auth_client
    old_cookie = client.cookies.get(auth.COOKIE_NAME)
    new_token = "NewPassword!中文123"

    response = client.post("/api/webui/auth/update", json={"new_token": new_token})

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert new_token not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert "HttpOnly" in response.headers["set-cookie"]
    assert client.cookies.get(auth.COOKIE_NAME) == token_manager.encode_cookie_token(new_token)
    assert not token_manager.verify_cookie_token(old_cookie)
    status = client.get("/api/webui/setup/status")
    assert status.status_code == 200
    assert status.json()["requires_custom_token"] is False
    assert status.json()["is_first_setup"] is True


def test_changing_configured_password_requires_login(auth_client):
    client, token_manager = auth_client
    assert token_manager.update_token("CurrentPassword!123")[0]
    client.cookies.clear()
    client.cookies.set(
        auth.COOKIE_NAME, token_manager.encode_cookie_token(token_manager.get_token()), domain="testserver.local"
    )
    old_cookie = client.cookies.get(auth.COOKIE_NAME)

    response = client.post("/api/webui/auth/update", json={"new_token": "NextPassword!456"})

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert not token_manager.verify_cookie_token(old_cookie)
    assert client.get("/api/webui/setup/status").status_code == 401


def test_invalid_password_preserves_current_login(auth_client):
    client, token_manager = auth_client
    old_cookie = client.cookies.get(auth.COOKIE_NAME)

    response = client.post("/api/webui/auth/update", json={"new_token": "lowercaseonly"})

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert "set-cookie" not in response.headers
    assert client.cookies.get(auth.COOKIE_NAME) == old_cookie
    assert client.get("/api/webui/setup/status").json()["requires_custom_token"] is True
    assert token_manager.verify_cookie_token(old_cookie)


def test_setting_first_password_requires_authentication(auth_client):
    client, token_manager = auth_client
    old_token = token_manager.get_token()
    client.cookies.clear()

    response = client.post("/api/webui/auth/update", json={"new_token": "NewPassword!123"})

    assert response.status_code == 401
    assert token_manager.get_token() == old_token
