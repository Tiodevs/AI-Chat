"""Provedor, circuit breaker e pool do banco com vida de processo. Seções 6.4 e 7.1 do SDD."""

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import event

from app.adapters.gemini_chat import GeminiChatProvider
from app.core.container import build_ai_runtime, ensure_ai_runtime, get_clock, get_settings
from app.db.session import pooled_engines
from app.main import create_app
from app.ports.chat import Message, TokenUsage, Tool, ToolResult
from tests.integration.test_auth import FrozenClock
from tests.integration.test_conversations import (
    VISITING,
    _ask,
    _configure,
    _create,
    _delete_guest,
    _events,
    _guest_secret,
)

pytestmark = pytest.mark.integration


class _FailingBackend:
    """Backend do Gemini que sempre falha com um erro sem nova tentativa. Conta as chamadas."""

    def __init__(self) -> None:
        self.calls = 0

    async def complete_structured(
        self,
        messages: list[Message],
        schema: type[BaseModel],
        temperature: float,
    ) -> tuple[BaseModel, TokenUsage]:
        del messages, schema, temperature
        self.calls += 1
        raise RuntimeError("gemini fora do ar")

    async def complete_with_tools(
        self,
        messages: list[Message],
        tools: list[Tool],
        temperature: float,
    ) -> tuple[ToolResult, TokenUsage]:
        del messages, tools, temperature
        self.calls += 1
        raise RuntimeError("gemini fora do ar")

    def stream(
        self,
        messages: list[Message],
        temperature: float,
    ) -> AsyncIterator[tuple[str, TokenUsage]]:
        raise AssertionError((messages, temperature))


def test_five_failures_in_different_requests_open_the_circuit(
    monkeypatch: pytest.MonkeyPatch,
    migrated_database: str,
) -> None:
    """CA-1 da Etapa 12.4: o sexto pedido degrada sem chamar o provedor (seção 7.1)."""
    _configure(monkeypatch, migrated_database)
    application = create_app()
    application.dependency_overrides[get_clock] = FrozenClock
    backend = _FailingBackend()
    chat = GeminiChatProvider(api_key="test-key", model="gemini-test", backend=backend)
    application.state.ai_runtime = build_ai_runtime(get_settings(), chat=chat)
    client = TestClient(application)
    created = _create(client)
    conversation_id = UUID(created.json()["id"])
    secret = _guest_secret(created)
    try:
        outcomes = [_events(_ask(client, conversation_id, VISITING).text)[-1] for _ in range(6)]
    finally:
        asyncio.run(_delete_guest(migrated_database, secret))
    assert outcomes[:5] == [("done", {"outcome": "error"})] * 5
    assert outcomes[5] == ("done", {"outcome": "degraded"})
    assert backend.calls == 5


def test_the_runtime_is_built_once_per_app(
    monkeypatch: pytest.MonkeyPatch,
    migrated_database: str,
) -> None:
    _configure(monkeypatch, migrated_database)
    first = create_app()
    second = create_app()
    settings = get_settings()
    runtime = ensure_ai_runtime(first.state, settings)
    assert ensure_ai_runtime(first.state, settings) is runtime
    assert ensure_ai_runtime(second.state, settings) is not runtime
    assert runtime.qa_workflow is ensure_ai_runtime(first.state, settings).qa_workflow


def test_requests_reuse_the_connections_of_the_pool(
    monkeypatch: pytest.MonkeyPatch,
    migrated_database: str,
) -> None:
    """CA-2 da Etapa 12.4: o lifespan abre um engine com pool, e os pedidos o reaproveitam."""
    _configure(monkeypatch, migrated_database)
    application = create_app()
    application.dependency_overrides[get_clock] = FrozenClock
    connects: list[int] = []
    checkouts: list[int] = []
    secret = ""
    try:
        with TestClient(application) as client:
            engines = pooled_engines(migrated_database)
            assert len(engines) == 1
            sync_engine = engines[0].sync_engine
            event.listen(sync_engine, "connect", lambda *_args: connects.append(1))
            event.listen(sync_engine, "checkout", lambda *_args: checkouts.append(1))
            created = _create(client)
            secret = _guest_secret(created)
            conversation_id = created.json()["id"]
            for _ in range(3):
                assert client.get(f"/v1/conversations/{conversation_id}").status_code == 200
    finally:
        if secret:
            asyncio.run(_delete_guest(migrated_database, secret))
    assert pooled_engines(migrated_database) == []
    assert len(checkouts) >= 6
    assert len(connects) <= 1
