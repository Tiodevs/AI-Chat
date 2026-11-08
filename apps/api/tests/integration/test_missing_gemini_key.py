"""A API sem `GEMINI_API_KEY` degrada em vez de devolver 500. Seções 7.1, 10.1, 17 e 22.1.

O primeiro deploy na Railway sobe antes de a chave existir. O fluxo de diagnóstico do teste
de fumaça não usa o modelo e precisa responder. Uma pergunta recebe a resposta fixa de
indisponibilidade, com o desfecho `error`.

A fixture `api` sobe a API com `APP_AI_ADAPTER=gemini` e a chave vazia, então as fábricas
montam o `UnavailableChatProvider` e o `UnavailableEmbeddingProvider`, sem rede. O embedding
falha com o `EmbeddingRequestError` do adaptador; a Etapa 13.2 leva esse erro para a porta.
Reaproveita os helpers de `test_conversations.py` e `test_auth.py`. O primeiro teste não usa
banco; os outros precisam de PostgreSQL com pgvector local (`migrated_database`), pulam sem
ele e falham com `REQUIRE_INTEGRATION_DB=1`.
"""

import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.adapters.chat_factory import build_chat_provider
from app.adapters.embedding_factory import build_embedding_provider
from app.adapters.gemini_embedding import EmbeddingRequestError
from app.adapters.unavailable import UnavailableChatProvider, UnavailableEmbeddingProvider
from app.core.config import Settings
from app.core.container import get_clock, get_settings
from app.domain.errors import ProviderUnavailable
from app.main import create_app
from app.ports.chat import RunContext
from app.prompts.qa import UNAVAILABLE
from app.workflows.qa import QuestionClassification
from tests.integration.test_auth import HMAC_KEY, FrozenClock
from tests.integration.test_conversations import (
    ORIGIN,
    VISITING,
    _ask,
    _create,
    _delete_guest,
    _events,
    _guest_secret,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch, migrated_database: str) -> TestClient:
    """API com `APP_AI_ADAPTER=gemini` e `GEMINI_API_KEY` vazia, como no primeiro deploy."""
    monkeypatch.setenv("DATABASE_URL", migrated_database)
    monkeypatch.setenv("RATE_LIMIT_HMAC_KEY", HMAC_KEY)
    monkeypatch.setenv("WEB_ORIGIN", ORIGIN)
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("APP_AI_ADAPTER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("LLM_DAILY_TOKEN_BUDGET", "0")
    get_settings.cache_clear()
    application = create_app()
    application.dependency_overrides[get_clock] = FrozenClock
    return TestClient(application)


def test_without_a_key_the_factories_return_providers_that_fail_on_use() -> None:
    settings = Settings(app_ai_adapter="gemini", gemini_api_key="", database_url="")
    chat = build_chat_provider(settings)
    embeddings = build_embedding_provider(settings)
    assert isinstance(chat, UnavailableChatProvider)
    assert isinstance(embeddings, UnavailableEmbeddingProvider)
    assert embeddings.dimensions == settings.embedding_dimensions

    def run() -> RunContext:
        return RunContext(
            run_id=uuid4(), request_id="nokey", prompt_version="test", trace_policy="metadata_only"
        )

    async def exercise() -> None:
        with pytest.raises(ProviderUnavailable):
            await chat.complete_structured([], QuestionClassification, run())
        with pytest.raises(ProviderUnavailable):
            async for _token in chat.stream([], run()):
                pass
        with pytest.raises(EmbeddingRequestError):
            await embeddings.embed_query("horário de visita")

    asyncio.run(exercise())


def test_the_diagnostics_stream_still_works_without_a_key(api: TestClient) -> None:
    response = api.get(
        "/v1/diagnostics/stream", headers={"X-Forwarded-For": f"nokey-{uuid4().hex}"}
    )
    assert response.status_code == 200, response.text
    assert [name for name, _payload in _events(response.text)] == ["tick", "tick", "tick"]


def test_a_question_without_a_key_gets_the_fixed_unavailable_answer(
    api: TestClient, migrated_database: str
) -> None:
    created = _create(api)
    assert created.status_code == 201, created.text
    secret = _guest_secret(created)
    try:
        response = _ask(api, UUID(created.json()["id"]), VISITING)
        events = _events(response.text)
    finally:
        asyncio.run(_delete_guest(migrated_database, secret))
    assert response.status_code == 200, response.text
    assert events[-1] == ("done", {"outcome": "error"})
    assert ("token", {"text": UNAVAILABLE}) in events
