import json
import sys

import pytest
from fastapi.testclient import TestClient

from app.core.container import get_settings
from app.main import create_app


def _client_with_database_url(monkeypatch: pytest.MonkeyPatch, database_url: str) -> TestClient:
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    return TestClient(create_app())


def test_health_returns_200_without_a_valid_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client_with_database_url(monkeypatch, "not-a-database")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "asyncpg" not in sys.modules
    assert "sqlalchemy" not in sys.modules


def test_health_returns_200_when_database_url_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200


def test_request_id_header_matches_the_log_line(capsys: pytest.CaptureFixture[str]) -> None:
    response = TestClient(create_app()).get("/health")
    request_id = response.headers["x-request-id"]
    assert request_id

    lines = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")
    ]
    matches = [line for line in lines if line.get("request_id") == request_id]
    assert matches
    log = matches[-1]
    assert log["event"] == "http.request"
    assert log["route"] == "/health"
    assert log["status_code"] == 200
    assert isinstance(log["duration_ms"], int)
    assert log["app_version"]
    assert "trace_id" in log
    assert "span_id" in log
    assert log["level"] == "info"
    assert log["timestamp"]


def test_route_log_uses_the_path_template(capsys: pytest.CaptureFixture[str]) -> None:
    app = create_app()

    @app.get("/_test/items/{item_id}")
    async def read_item(item_id: str) -> dict[str, str]:
        return {"item_id": item_id}

    response = TestClient(app).get("/_test/items/123")
    assert response.status_code == 200
    request_id = response.headers["x-request-id"]
    lines = [
        json.loads(line)
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("{") and f'"request_id": "{request_id}"' in line
    ]
    assert lines[-1]["route"] == "/_test/items/{item_id}"
