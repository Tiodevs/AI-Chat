import pytest
from fastapi.testclient import TestClient

from app.core.container import get_settings
from app.main import create_app
from app.prompts.auth import BAD_ORIGIN, EDGE_FORBIDDEN, VALIDATION

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
    monkeypatch.setenv("PRIVACY_CONTACT_EMAIL", "privacidade@harborlight.example")
    client = _client(monkeypatch)
    response = client.get("/v1/legal/versions")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "terms": "2026-10-25.1",
        "privacy_notice": "2026-10-25.1",
        "privacy_contact_email": "privacidade@harborlight.example",
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


EDGE_SECRET = "segredo-da-borda"


def _cloud_client(monkeypatch: pytest.MonkeyPatch, *, edge_secret: str = EDGE_SECRET) -> TestClient:
    monkeypatch.setenv("WEB_ORIGIN", ORIGIN)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("LLM_DAILY_TOKEN_BUDGET", "1000")
    monkeypatch.setenv("RATE_LIMIT_HMAC_KEY", "hmac-key")
    monkeypatch.setenv("PSEUDONYM_KEY", "pseudonym-key")
    monkeypatch.setenv("METRICS_TOKEN", "metrics-token")
    monkeypatch.setenv("EDGE_SECRET", edge_secret)
    get_settings.cache_clear()
    return TestClient(create_app())


def test_direct_request_to_v1_without_the_edge_secret_is_forbidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CA-1 da Etapa 12.5: quem chama a Railway direto não chega a /v1."""
    client = _cloud_client(monkeypatch)
    responses = [
        client.get("/v1/legal/versions"),
        client.get("/v1/legal/versions", headers={"x-atrium-edge": "outro"}),
        client.post("/v1/conversations", headers={"Origin": ORIGIN, "X-Forwarded-For": "1.2.3.4"}),
    ]
    for response in responses:
        assert response.status_code == 403
        body = response.json()
        assert body["error"]["code"] == "forbidden"
        assert body["error"]["message"] == EDGE_FORBIDDEN
        assert body["error"]["request_id"] == response.headers["x-request-id"]
        assert response.headers["cache-control"] == "no-store"


def test_request_with_the_edge_secret_reaches_v1(monkeypatch: pytest.MonkeyPatch) -> None:
    """CA-3 da Etapa 12.5: pela Vercel, que manda o segredo, o app funciona como antes."""
    response = _cloud_client(monkeypatch).get(
        "/v1/legal/versions",
        headers={"x-atrium-edge": EDGE_SECRET},
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"


def test_health_ready_and_metrics_stay_reachable_without_the_edge_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CA-2 da Etapa 12.5: a Railway e o Prometheus chamam a API direto."""
    client = _cloud_client(monkeypatch)
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code != 403
    metrics = client.get("/metrics", headers={"Authorization": "Bearer metrics-token"})
    assert metrics.status_code == 200


@pytest.mark.parametrize("app_env", ["local", "test"])
def test_local_and_test_do_not_require_the_edge_secret(
    monkeypatch: pytest.MonkeyPatch,
    app_env: str,
) -> None:
    monkeypatch.setenv("WEB_ORIGIN", ORIGIN)
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("EDGE_SECRET", EDGE_SECRET)
    get_settings.cache_clear()
    assert TestClient(create_app()).get("/v1/legal/versions").status_code == 200


def test_cloud_without_edge_secret_keeps_v1_open_until_the_railway_has_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Etapa 12.5a: a API só exige o cabeçalho depois que EDGE_SECRET chega à Railway."""
    client = _cloud_client(monkeypatch, edge_secret="")
    assert client.get("/v1/legal/versions").status_code == 200
