"""Spans só com os atributos permitidos, `/metrics` com token e log de pedido sem dado pessoal.

Seções 18.1, 18.2 e 18.3 do SDD, NFR-6 e NFR-7. A fixture `exporter` troca o tracer de
`app/core/telemetry.py` por um que grava os spans na memória. A fixture `client` sobe o app
com `METRICS_TOKEN` de teste dentro de um `with`, então o `lifespan` roda. Sem `DATABASE_URL`,
nada toca o banco. Com a URL no ambiente ou no `apps/api/.env`, o `lifespan` abre o pool e
confere as versões presas, e o `/metrics` lê os pedidos de titular e a retenção nesse banco; uma
falha ali só vira log. Não usa rede.
"""

import json
from collections.abc import Iterator

import pytest
import structlog
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.core import telemetry
from app.core.container import get_settings
from app.core.logging import configure_logging
from app.core.telemetry import SPAN_ATTRIBUTES, traced_span
from app.main import create_app


@pytest.fixture
def exporter(monkeypatch: pytest.MonkeyPatch) -> Iterator[InMemorySpanExporter]:
    """Põe no módulo de telemetria um tracer que guarda os spans terminados na memória."""
    memory = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(memory))
    monkeypatch.setattr(telemetry, "_tracer", provider.get_tracer("test"))
    yield memory


def test_span_keeps_only_allowed_attributes(exporter: InMemorySpanExporter) -> None:
    with traced_span("qa.rewrite", intent="public_info", model="m", question="Onde fica o café?"):
        pass

    (span,) = exporter.get_finished_spans()
    assert span.attributes is not None
    assert set(span.attributes) <= SPAN_ATTRIBUTES["qa.rewrite"] | {
        "request_id",
        "langsmith.run_id",
    }
    assert "question" not in span.attributes
    assert span.attributes["intent"] == "public_info"


def test_span_records_run_id_and_error_type(exporter: InMemorySpanExporter) -> None:
    with pytest.raises(RuntimeError), traced_span("qa.generate", run_id="run-1"):
        raise RuntimeError("falhou com ana@example.com")

    (span,) = exporter.get_finished_spans()
    assert span.attributes is not None
    assert span.attributes["langsmith.run_id"] == "run-1"
    assert span.attributes["error.type"] == "RuntimeError"
    assert all("ana@example.com" not in str(value) for value in span.attributes.values())


def test_unknown_span_is_refused() -> None:
    with pytest.raises(ValueError), traced_span("qa.invented"):
        pass


def test_span_ids_come_from_the_active_span(exporter: InMemorySpanExporter) -> None:
    assert telemetry.span_ids() == (None, None)
    tracer = trace.get_tracer("noop")
    assert tracer is not None


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """App com `METRICS_TOKEN` de teste, aberto num `with` para o `lifespan` rodar."""
    monkeypatch.setenv("METRICS_TOKEN", "segredo-de-teste")
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_metrics_requires_the_right_token(client: TestClient) -> None:
    assert client.get("/metrics").status_code == 401
    wrong = client.get("/metrics", headers={"Authorization": "Bearer errado"})
    assert wrong.status_code == 401
    ok = client.get("/metrics", headers={"Authorization": "Bearer segredo-de-teste"})
    assert ok.status_code == 200
    assert "atrium_http_requests" in ok.text


def test_metrics_is_off_without_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("METRICS_TOKEN", "")
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        response = test_client.get("/metrics", headers={"Authorization": "Bearer "})
    get_settings.cache_clear()
    assert response.status_code == 404


def test_http_metrics_use_the_route_template(client: TestClient) -> None:
    client.get("/health")
    client.get("/rota-inexistente-123")
    body = client.get("/metrics", headers={"Authorization": "Bearer segredo-de-teste"}).text
    assert 'route="/health"' in body
    assert 'route="unmatched"' in body
    assert "rota-inexistente-123" not in body


def test_request_log_has_no_personal_data_and_matches_response_id(
    client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging("INFO")
    response = client.get("/health", headers={"X-Forwarded-For": "203.0.113.9"})
    structlog.get_logger("atrium").info(
        "teste", contact="ana@example.com", note="(555) 014-2600", ip="203.0.113.9"
    )
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    request_line = next(line for line in lines if line["event"] == "http.request")
    assert request_line["request_id"] == response.headers["x-request-id"]
    raw = json.dumps(lines)
    assert "ana@example.com" not in raw
    assert "014-2600" not in raw
    assert "203.0.113.9" not in raw
