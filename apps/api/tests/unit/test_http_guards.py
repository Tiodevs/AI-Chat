import pytest
from fastapi.testclient import TestClient

from app.core.container import get_settings
from app.main import create_app
from app.prompts.auth import BAD_ORIGIN, VALIDATION

ORIGIN = "http://localhost:5173"


def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("WEB_ORIGIN", ORIGIN)
    monkeypatch.setenv("APP_ENV", "local")
    get_settings.cache_clear()
    return TestClient(create_app())


def test_state_changing_request_with_another_origin_is_bad_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _client(monkeypatch).post(
        "/v1/auth/logout",
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "bad_origin"
    assert body["error"]["message"] == BAD_ORIGIN
    assert body["error"]["request_id"] == response.headers["x-request-id"]
    assert response.headers["cache-control"] == "no-store"


def test_state_changing_request_without_origin_is_bad_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _client(monkeypatch).put("/v1/me")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "bad_origin"


def test_get_does_not_require_origin_and_v1_is_not_stored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(monkeypatch)
    response = client.get("/v1/legal/versions")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "terms": "2026-10-25.1",
        "privacy_notice": "2026-10-25.1",
    }
    assert client.get("/health").headers.get("cache-control") is None


def test_validation_uses_the_section_12_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _client(monkeypatch).post(
        "/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={},
    )
    assert response.status_code == 422
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == VALIDATION
    assert "retry_after_seconds" not in body["error"]


def test_cors_allows_only_the_frontend_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    allowed = client.options(
        "/v1/auth/login",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
        },
    )
    refused = client.options(
        "/v1/auth/login",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert allowed.headers["access-control-allow-origin"] == ORIGIN
    assert "access-control-allow-origin" not in refused.headers
