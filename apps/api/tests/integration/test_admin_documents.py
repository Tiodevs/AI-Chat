"""Gestão de documentos pelo admin contra o PostgreSQL. Etapa 7.1, CA-1 a CA-5.

Seções 7.3, 8.2, 10.4 e 12 do SDD. A ingestão roda na tarefa de fundo, que o TestClient
termina antes de devolver a resposta.
"""

import asyncio
from collections.abc import Coroutine, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.adapters.clock import SystemClock
from app.adapters.deterministic_embedding import DeterministicEmbeddingProvider
from app.adapters.password_hasher import get_password_hasher
from app.adapters.text_extractor import FileTextExtractor
from app.core.container import get_document_admin_service, get_settings
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.auth import bucket_key
from app.domain.documents import MAX_UPLOAD_BYTES, UPLOAD_LIMIT, UPLOAD_PURPOSE, upload_window_start
from app.domain.legal import LEGAL_DOCUMENT_VERSION
from app.domain.registration import ConsentGrant, Purpose
from app.main import create_app
from app.prompts.corpus import EMBED_FAILED
from app.prompts.documents import STILL_PROCESSING, UPLOADS_LIMITED
from app.repositories.consents import ConsentRepository
from app.repositories.documents import DocumentRepository
from app.repositories.rate_limits import RateLimitRepository
from app.repositories.users import UserRepository
from app.services.documents import DocumentAdminService
from app.services.ingestion import IngestionService
from app.services.retrieval import RetrievalService

pytestmark = pytest.mark.integration

ORIGIN = "http://localhost:5173"
HMAC_KEY = "test-hmac-key"
PASSWORD = "correct-horse-1"
QUESTION = "Onde estaciono no Harborlight?"


@dataclass
class _Embeddings:
    """Um vetor só para todo texto. Pode falhar ou olhar a busca durante a ingestão."""

    vector: list[float]
    fail: bool = False
    probe: Any = None
    seen_during: list[list[str]] = field(default_factory=list)
    model_name: str = "same"
    dimensions: int = 0

    def __post_init__(self) -> None:
        self.dimensions = len(self.vector)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if self.probe is not None:
            self.seen_during.append(await self.probe())
        if self.fail:
            raise RuntimeError("embedding down")
        return [self.vector for _ in texts]

    async def embed_query(self, text_: str) -> list[float]:
        del text_
        return self.vector


@dataclass
class _Harness:
    client: TestClient
    database_url: str
    embeddings: _Embeddings
    admin_id: UUID
    admin_email: str


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch, migrated_database: str) -> Iterator[_Harness]:
    monkeypatch.setenv("DATABASE_URL", migrated_database)
    monkeypatch.setenv("RATE_LIMIT_HMAC_KEY", HMAC_KEY)
    monkeypatch.setenv("WEB_ORIGIN", ORIGIN)
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("APP_AI_ADAPTER", "fake")
    get_settings.cache_clear()
    vector = _run(DeterministicEmbeddingProvider().embed_query(QUESTION))
    embeddings = _Embeddings(vector=vector)
    application = create_app()

    def service() -> DocumentAdminService:
        return DocumentAdminService(
            database_url=migrated_database,
            clock=SystemClock(),
            hmac_key=HMAC_KEY,
            ingestion=IngestionService(migrated_database, embeddings, FileTextExtractor()),
        )

    application.dependency_overrides[get_document_admin_service] = service
    email = f"docs-admin-{uuid4().hex}@example.com"
    admin_id = _run(_insert_user(migrated_database, email, "admin"))
    client = TestClient(application)
    _login(client, email)
    try:
        yield _Harness(client, migrated_database, embeddings, admin_id, email)
    finally:
        _run(_cleanup(migrated_database, admin_id))


def test_uploads_above_ten_megabytes_or_of_other_types_are_refused(harness: _Harness) -> None:
    """CA-1 (FR-10, NFR-10)."""
    cases = [
        ("contrato.docx", b"PK\x03\x04conteudo", "file"),
        ("grande.md", b"a" * (MAX_UPLOAD_BYTES + 1), "file"),
        ("falso.pdf", b"# nao sou pdf", "file"),
    ]
    for filename, data, failing_field in cases:
        response = _upload(harness.client, filename, data)
        assert response.status_code == 422, filename
        error = response.json()["error"]
        assert error["code"] == "validation_error"
        assert set(error["field_errors"]) == {failing_field}
    assert _run(_document_count(harness.database_url, harness.admin_id)) == 0


def test_an_upload_starts_processing_ends_ready_and_is_audited(harness: _Harness) -> None:
    """Passos da seção 7.3 e CA-4 (document.upload)."""
    response = _upload(
        harness.client,
        "estacionamento.md",
        b"# Estacionamento\n\nO estacionamento fica no subsolo, entrada pela Rua A.",
        title="Estacionamento",
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["latest_version"]["ingestion_status"] == "processing"
    assert body["active_version"] is None
    assert body["slug"] == "estacionamento" or body["slug"].startswith("estacionamento-")

    listed = _find(harness.client, body["id"])
    assert listed["title"] == "Estacionamento"
    assert listed["status"] == "active"
    assert listed["active_version"]["version"] == 1
    assert listed["active_version"]["media_type"] == "text/markdown"
    assert listed["latest_version"]["ingestion_status"] == "ready"
    assert "Rua A" in " ".join(_run(_searchable(harness, body["slug"])))
    assert _run(_actions(harness.database_url, harness.admin_id)) == ["document.upload"]


def test_during_a_replacement_the_previous_version_keeps_answering(harness: _Harness) -> None:
    """CA-2 (FR-11) e CA-4 (document.replace)."""
    document = _upload(harness.client, "vagas.md", b"# Vagas\n\nVersao antiga: Rua A.").json()
    slug = document["slug"]

    async def probe() -> list[str]:
        return await _searchable(harness, slug)

    harness.embeddings.probe = probe
    new_text = b"# Vagas\n\nVersao nova: Rua B."
    replaced = _replace(harness.client, document["id"], "vagas.md", new_text)
    assert replaced.status_code == 202, replaced.text
    assert replaced.json()["active_version"]["version"] == 1
    assert replaced.json()["latest_version"]["ingestion_status"] == "processing"

    during = " ".join(harness.embeddings.seen_during[-1])
    assert "Rua A" in during
    assert "Rua B" not in during
    after = " ".join(_run(_searchable(harness, slug)))
    assert "Rua B" in after
    assert "Rua A" not in after
    assert _find(harness.client, document["id"])["active_version"]["version"] == 2
    assert _run(_actions(harness.database_url, harness.admin_id)) == [
        "document.upload",
        "document.replace",
    ]


def test_a_failed_replacement_keeps_the_previous_version_and_retry_recovers(
    harness: _Harness,
) -> None:
    """CA-2 (FR-11), ação Retry e CA-4 (document.retry)."""
    document = _upload(harness.client, "guia.txt", "Guia antigo: café às 9h.".encode()).json()
    harness.embeddings.fail = True
    replaced = _replace(harness.client, document["id"], "guia.txt", b"Guia novo: cafe as 10h.")
    assert replaced.status_code == 202

    failed = _find(harness.client, document["id"])
    assert failed["latest_version"]["ingestion_status"] == "failed"
    assert failed["latest_version"]["error"] == EMBED_FAILED
    assert failed["active_version"]["version"] == 1
    assert "9h" in " ".join(_run(_searchable(harness, document["slug"])))

    harness.embeddings.fail = False
    retried = harness.client.post(
        f"/v1/admin/documents/{document['id']}/retry", headers={"Origin": ORIGIN}
    )
    assert retried.status_code == 202, retried.text
    recovered = _find(harness.client, document["id"])
    assert recovered["active_version"]["version"] == 3
    assert recovered["latest_version"]["ingestion_status"] == "ready"
    assert "10h" in " ".join(_run(_searchable(harness, document["slug"])))
    again = harness.client.post(
        f"/v1/admin/documents/{document['id']}/retry", headers={"Origin": ORIGIN}
    )
    assert again.status_code == 409
    assert _run(_actions(harness.database_url, harness.admin_id)) == [
        "document.upload",
        "document.replace",
        "document.retry",
    ]


def test_archiving_takes_the_document_out_of_the_answers(harness: _Harness) -> None:
    """CA-3 (FR-12) e CA-4 (document.archive)."""
    document = _upload(harness.client, "lanchonete.md", b"# Lanchonete\n\nAbre as 7h.").json()
    assert "7h" in " ".join(_run(_searchable(harness, document["slug"])))

    archived = harness.client.post(
        f"/v1/admin/documents/{document['id']}/archive", headers={"Origin": ORIGIN}
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["status"] == "archived"
    assert _run(_searchable(harness, document["slug"])) == []
    twice = harness.client.post(
        f"/v1/admin/documents/{document['id']}/archive", headers={"Origin": ORIGIN}
    )
    assert twice.status_code == 200
    blocked = _replace(harness.client, document["id"], "lanchonete.md", b"# L\n\nAbre as 8h.")
    assert blocked.status_code == 409
    assert _run(_actions(harness.database_url, harness.admin_id)) == [
        "document.upload",
        "document.archive",
    ]


def test_a_replacement_waits_for_a_version_still_processing(harness: _Harness) -> None:
    document = _upload(harness.client, "farmacia.md", b"# Farmacia\n\nTerreo.").json()
    _run(_insert_processing_version(harness.database_url, UUID(document["id"])))
    response = _replace(harness.client, document["id"], "farmacia.md", b"# Farmacia\n\n1o andar.")
    assert response.status_code == 409
    assert response.json()["error"]["message"] == STILL_PROCESSING


def test_uploads_above_thirty_per_hour_return_429(harness: _Harness) -> None:
    """Balde de uploads da seção 10.4."""
    _run(_fill_upload_bucket(harness.database_url, harness.admin_id))
    response = _upload(harness.client, "extra.md", b"# Extra\n\nTexto.")
    assert response.status_code == 429
    error = response.json()["error"]
    assert error["code"] == "rate_limited"
    assert error["message"] == UPLOADS_LIMITED
    assert error["retry_after_seconds"] > 0
    assert _run(_document_count(harness.database_url, harness.admin_id)) == 0


def test_a_member_gets_403_and_a_visitor_401_on_document_routes(harness: _Harness) -> None:
    """CA-5."""
    member_email = f"docs-member-{uuid4().hex}@example.com"
    member_id = _run(_insert_user(harness.database_url, member_email, "member"))
    try:
        member = TestClient(harness.client.app)
        _login(member, member_email)
        guest = TestClient(harness.client.app)
        target = uuid4()
        for client, status in ((member, 403), (guest, 401)):
            calls = [
                client.get("/v1/admin/documents"),
                _upload(client, "a.md", b"# A"),
                _replace(client, str(target), "a.md", b"# A"),
                client.post(f"/v1/admin/documents/{target}/retry", headers={"Origin": ORIGIN}),
                client.post(f"/v1/admin/documents/{target}/archive", headers={"Origin": ORIGIN}),
            ]
            assert [call.status_code for call in calls] == [status] * 5
        assert _run(_document_count(harness.database_url, member_id)) == 0
    finally:
        _run(_cleanup(harness.database_url, member_id))


def _upload(
    client: TestClient, filename: str, data: bytes, *, title: str | None = None
) -> Any:
    return client.post(
        "/v1/admin/documents",
        headers={"Origin": ORIGIN},
        files={"file": (filename, data, "application/octet-stream")},
        data={} if title is None else {"title": title},
    )


def _replace(client: TestClient, document_id: str, filename: str, data: bytes) -> Any:
    return client.post(
        f"/v1/admin/documents/{document_id}/replace",
        headers={"Origin": ORIGIN},
        files={"file": (filename, data, "application/octet-stream")},
    )


def _find(client: TestClient, document_id: str) -> dict[str, Any]:
    response = client.get("/v1/admin/documents")
    assert response.status_code == 200, response.text
    matches = [item for item in response.json()["documents"] if item["id"] == document_id]
    assert len(matches) == 1
    found: dict[str, Any] = matches[0]
    return found


def _login(client: TestClient, email: str) -> None:
    response = client.post(
        "/v1/auth/login",
        headers={"Origin": ORIGIN, "X-Forwarded-For": f"docs-{uuid4().hex}"},
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text


def _run(coro: Coroutine[object, object, Any]) -> Any:
    return asyncio.run(coro)


async def _searchable(harness: _Harness, slug: str) -> list[str]:
    """Conteúdo que a busca híbrida devolve para este documento. Seção 8.2."""
    hits = await RetrievalService(
        harness.database_url, harness.embeddings, minimum_similarity=0.5
    ).search_by_vector(QUESTION, harness.embeddings.vector)
    return [hit.content for hit in hits if hit.document_slug == slug]


async def _insert_user(database_url: str, email: str, role: str) -> UUID:
    async with open_session(database_url) as session, UnitOfWork(session):
        user_id = await UserRepository(session).insert(
            email=email,
            password_hash=get_password_hasher().hash_password(PASSWORD),
            full_name="Pessoa Teste",
            role=role,
            now=datetime.now(UTC),
        )
        await ConsentRepository(session).insert_grants(
            user_id=user_id,
            grants=(ConsentGrant(Purpose.TERMS.value, LEGAL_DOCUMENT_VERSION),),
            source="form",
            granted_at=datetime.now(UTC),
        )
    assert isinstance(user_id, UUID)
    return user_id


async def _insert_processing_version(database_url: str, document_id: UUID) -> None:
    async with open_session(database_url) as session, UnitOfWork(session):
        repository = DocumentRepository(session)
        await repository.insert_version(
            document_id=document_id,
            version=await repository.next_version(document_id),
            filename="farmacia.md",
            media_type="text/markdown",
            sha256="0" * 64,
            original_bytes=b"# Farmacia",
        )


async def _fill_upload_bucket(database_url: str, admin_id: UUID) -> None:
    now = datetime.now(UTC)
    key = bucket_key(purpose=UPLOAD_PURPOSE, subject=str(admin_id), day=now.date(), key=HMAC_KEY)
    async with open_session(database_url) as session, UnitOfWork(session):
        repository = RateLimitRepository(session)
        for _ in range(UPLOAD_LIMIT):
            await repository.increment(key, upload_window_start(now))


async def _document_count(database_url: str, created_by: UUID) -> int:
    async with open_session(database_url) as session:
        value = await session.scalar(
            text("SELECT count(*) FROM documents WHERE created_by = :id"), {"id": created_by}
        )
    return int(value or 0)


async def _actions(database_url: str, actor: UUID) -> list[str]:
    async with open_session(database_url) as session:
        result = await session.execute(
            text(
                "SELECT action FROM audit_events WHERE actor_user_id = :actor "
                "AND target_type = 'document' ORDER BY created_at, action"
            ),
            {"actor": actor},
        )
    return [str(value) for value in result.scalars()]


async def _cleanup(database_url: str, user_id: UUID) -> None:
    async with open_session(database_url) as session, UnitOfWork(session):
        scope = "SELECT id FROM documents WHERE created_by = :user_id"
        versions = f"SELECT id FROM document_versions WHERE document_id IN ({scope})"
        statements = [
            f"UPDATE documents SET active_version = NULL WHERE id IN ({scope})",
            f"DELETE FROM chunks WHERE document_version_id IN ({versions})",
            f"DELETE FROM document_versions WHERE document_id IN ({scope})",
            "DELETE FROM documents WHERE created_by = :user_id",
            "DELETE FROM audit_events WHERE actor_user_id = :user_id",
            "DELETE FROM auth_sessions WHERE user_id = :user_id",
            "DELETE FROM consent_records WHERE user_id = :user_id",
            "DELETE FROM users WHERE id = :user_id",
        ]
        for statement in statements:
            await session.execute(text(statement), {"user_id": user_id})
