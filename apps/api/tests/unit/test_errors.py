from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.core.errors import status_for
from app.domain.errors import (
    BadOrigin,
    BudgetExceeded,
    CircuitOpen,
    Conflict,
    DomainError,
    DuplicateMessage,
    Forbidden,
    NotFound,
    ProviderUnavailable,
    RateLimited,
    Unauthenticated,
    ValidationFailed,
)
from app.main import create_app


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (NotFound("x"), 404, "not_found"),
        (Conflict("x"), 409, "conflict"),
        (Forbidden("x"), 403, "forbidden"),
        (BadOrigin("x"), 403, "bad_origin"),
        (Unauthenticated("x"), 401, "unauthenticated"),
        (ValidationFailed("x"), 422, "validation_error"),
        (RateLimited("x", retry_after_seconds=15), 429, "rate_limited"),
        (BudgetExceeded("x"), 503, "degraded"),
        (ProviderUnavailable("x"), 503, "provider_unavailable"),
        (CircuitOpen("x"), 503, "provider_unavailable"),
    ],
)
def test_domain_error_status_and_code(error: DomainError, status: int, code: str) -> None:
    assert status_for(error) == status
    assert error.code == code


def test_domain_error_uses_the_section_12_envelope() -> None:
    app = create_app()

    @app.get("/_test/missing")
    async def missing() -> None:
        raise NotFound("Não encontrado.")

    response = TestClient(app).get("/_test/missing")
    assert response.status_code == 404
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "request_id"}
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "Não encontrado."
    assert body["error"]["request_id"] == response.headers["x-request-id"]


def test_duplicate_message_envelope_includes_the_existing_id() -> None:
    app = create_app()
    message_id = UUID("00000000-0000-4000-8000-000000000010")

    @app.get("/_test/duplicate")
    async def duplicate() -> None:
        raise DuplicateMessage("Esta mensagem já foi enviada.", message_id=message_id)

    response = TestClient(app).get("/_test/duplicate")
    assert response.status_code == 409
    body = response.json()["error"]
    assert body["code"] == "conflict"
    assert body["message_id"] == str(message_id)
    assert "retry_after_seconds" not in body


def test_field_errors_appear_only_when_the_domain_sets_them() -> None:
    app = create_app()

    @app.get("/_test/fields")
    async def fields() -> None:
        raise ValidationFailed(
            "Não foi possível concluir o cadastro.",
            field_errors={"email": "Digite um e-mail válido."},
        )

    response = TestClient(app).get("/_test/fields")
    body = response.json()["error"]
    assert response.status_code == 422
    assert body["field_errors"] == {"email": "Digite um e-mail válido."}
    assert "retry_after_seconds" not in body


def test_rate_limit_envelope_includes_retry_after_seconds() -> None:
    app = create_app()

    @app.get("/_test/limited")
    async def limited() -> None:
        raise RateLimited("E-mail ou senha incorretos.", retry_after_seconds=90)

    response = TestClient(app).get("/_test/limited")
    assert response.status_code == 429
    assert response.json()["error"]["retry_after_seconds"] == 90
    assert response.json()["error"]["code"] == "rate_limited"
