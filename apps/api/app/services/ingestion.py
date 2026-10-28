"""Ingestão síncrona: extrair, dividir, embedar e publicar. Seção 7.3 do SDD."""

from datetime import timedelta
from uuid import UUID, uuid4

import structlog

from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.chunking import split_markdown
from app.domain.embedding_text import document_embedding_text
from app.domain.trace_policy import ingestion_event
from app.ports.clock import Clock
from app.ports.embedding import EmbeddingProvider
from app.ports.text_extractor import TextExtractor
from app.ports.tracing import NullTracer, TraceRecorder
from app.prompts.corpus import EMBED_FAILED, EMPTY_DOCUMENT, PROCESSING_TIMED_OUT
from app.repositories.documents import DocumentRepository, NewChunk

STALE_PROCESSING_AFTER = timedelta(minutes=15)


class IngestionService:
    def __init__(
        self,
        database_url: str,
        embeddings: EmbeddingProvider,
        extractor: TextExtractor,
        tracer: TraceRecorder | None = None,
    ) -> None:
        self._database_url = database_url
        self._embeddings = embeddings
        self._extractor = extractor
        self._tracer = tracer or NullTracer()

    async def ingest_new_version(
        self,
        *,
        slug: str,
        title: str,
        filename: str,
        media_type: str,
        data: bytes,
        sha256: str,
        created_by: UUID,
    ) -> str:
        version_id = await self._open_version(
            slug=slug,
            title=title,
            filename=filename,
            media_type=media_type,
            sha256=sha256,
            data=data,
            created_by=created_by,
        )
        body = ""
        try:
            body = await self._extractor.extract(data, media_type)
            drafts = split_markdown(body)
            if not body.strip() or not drafts:
                await self._fail(version_id, EMPTY_DOCUMENT, body)
                return "failed"
            texts = [
                document_embedding_text(title, draft.heading, draft.content) for draft in drafts
            ]
            vectors = await self._embeddings.embed_documents(texts)
            if len(vectors) != len(drafts):
                await self._fail(version_id, EMBED_FAILED, body)
                return "failed"
            chunks = [
                NewChunk(index, draft.heading, draft.content, vector)
                for index, (draft, vector) in enumerate(zip(drafts, vectors, strict=True))
            ]
            await self._publish(
                slug=slug,
                version_id=version_id,
                title=title,
                body_text=body,
                chunks=chunks,
            )
        except Exception:
            _log("warning", "ingestion.failed", slug=slug, error_type="embedding")
            await self._fail(version_id, EMBED_FAILED, body)
            return "failed"
        try:
            self._tracer.record_many(
                (
                    ingestion_event(
                        run_id=uuid4(),
                        slug=slug,
                        body=body,
                    ),
                )
            )
        except Exception:
            _log("warning", "ingestion.trace_failed", slug=slug)
        _log("info", "ingestion.ready", slug=slug, chunks=len(chunks))
        return "embedded"

    async def _open_version(
        self,
        *,
        slug: str,
        title: str,
        filename: str,
        media_type: str,
        sha256: str,
        data: bytes,
        created_by: UUID,
    ) -> UUID:
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = DocumentRepository(session)
            document_id = await repository.ensure_document(
                slug=slug,
                title=title,
                created_by=created_by,
            )
            number = await repository.next_version(document_id)
            version_id = await repository.insert_version(
                document_id=document_id,
                version=number,
                filename=filename,
                media_type=media_type,
                sha256=sha256,
                original_bytes=data,
            )
        return version_id

    async def _publish(
        self,
        *,
        slug: str,
        version_id: UUID,
        title: str,
        body_text: str,
        chunks: list[NewChunk],
    ) -> None:
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = DocumentRepository(session)
            document_id = await repository.id_for_slug(slug)
            if document_id is None:
                raise RuntimeError(slug)
            await repository.publish(
                document_id=document_id,
                version_id=version_id,
                title=title,
                body_text=body_text,
                chunks=chunks,
            )

    async def _fail(self, version_id: UUID, error: str, body_text: str) -> None:
        async with open_session(self._database_url) as session, UnitOfWork(session):
            await DocumentRepository(session).mark_failed(version_id, error, body_text)


async def fail_stale_processing_versions(database_url: str, clock: Clock) -> int:
    deadline = clock.now() - STALE_PROCESSING_AFTER
    async with open_session(database_url) as session, UnitOfWork(session):
        changed = await DocumentRepository(session).fail_stale(deadline, PROCESSING_TIMED_OUT)
    return changed


def _log(level: str, event: str, **fields: object) -> None:
    try:
        getattr(structlog.get_logger("atrium"), level)(event, **fields)
    except Exception:
        return
