"""O `/ready` responde 503 e registra o motivo quando o banco falta ou não responde. NFR-9.

Seção 12 do SDD (`GET /ready`) e NFR-7. Cada teste troca a `DATABASE_URL` com `monkeypatch`,
limpa o cache de `get_settings` e chama a rota por um `TestClient(create_app())`, sem
`lifespan`. As URLs são vazia, inválida ou apontam para a porta 1 local, que recusa a conexão,
então nenhum banco de verdade é usado. Os motivos `vector_missing` e `dimension_mismatch`
precisam de um PostgreSQL e ficam em `tests/integration/test_database.py`.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.core.container import get_settings
from app.main import create_app


def _events(capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    """Lê os eventos JSON que o `structlog` escreveu na stdout capturada."""
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
    # A senha na URL serve para provar que a falha de conexão não a leva para o log (NFR-7).
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
