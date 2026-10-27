import json

import pytest
from fastapi.testclient import TestClient

from app.core.container import get_settings
from app.main import create_app


def _events(capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    captured = capsys.readouterr().out
    return [json.loads(line) for line in captured.splitlines() if line.startswith("{")]


def test_ready_fails_when_the_database_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("DATABASE_URL", "")
    get_settings.cache_clear()
    response = TestClient(create_app()).get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert response.headers["x-request-id"]
    reasons = [
        event.get("reason") for event in _events(capsys) if event.get("event") == "readiness.failed"
    ]
    assert reasons == ["database_unconfigured"]


def test_ready_fails_when_the_database_is_unreachable(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://atrium:super-secret-password@127.0.0.1:1/atrium",
    )
    get_settings.cache_clear()
    client = TestClient(create_app())
    assert client.get("/health").status_code == 200
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    output = capsys.readouterr().out
    assert "super-secret-password" not in output
    events = [json.loads(line) for line in output.splitlines() if line.startswith("{")]
    reasons = [event.get("reason") for event in events if event.get("event") == "readiness.failed"]
    assert reasons == ["database_unreachable"]


def test_ready_fails_when_the_database_url_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "not-a-database")
    get_settings.cache_clear()
    response = TestClient(create_app()).get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
