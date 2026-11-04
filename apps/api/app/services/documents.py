"""Gestão de documentos pelo admin: listar, enviar, substituir, tentar de novo e arquivar.

Seções 7.3, 8.1, 10.4 e 12 do SDD. A versão nasce em `processing` na mesma transação que
grava a auditoria. A ingestão roda depois, fora do pedido, e só troca a versão ativa no
sucesso (FR-11).
"""

import hashlib
from dataclasses import dataclass
from datetime import UTC
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.auth import bucket_key
from app.domain.documents import (
    UPLOAD_PURPOSE,
    AcceptedFile,
    DocumentAction,
    DocumentView,
    UploadIssue,
    check_file,
    clean_title,
    numbered_slug,
    processing_is_recent,
    slugify,
    stem_of,
    upload_rate_decision,
    upload_window_start,
)
from app.domain.errors import Conflict, NotFound, RateLimited, ValidationFailed
from app.ports.clock import Clock
from app.prompts.documents import (
    DOCUMENT_ARCHIVED,
    DOCUMENT_NOT_FOUND,
    NOTHING_TO_RETRY,
    STILL_PROCESSING,
    UPLOAD_INVALID,
    UPLOADS_LIMITED,
    issue_message,
)
from app.repositories.audit import AuditRepository
from app.repositories.documents import DocumentRepository
from app.repositories.rate_limits import RateLimitRepository
from app.services.ingestion import IngestionService

TARGET_TYPE = "document"


@dataclass(frozen=True, slots=True)
class IngestionJob:
    """O que a tarefa de fundo precisa para os passos 2 a 6 da seção 7.3."""

    version_id: UUID
    slug: str
    title: str
    media_type: str
    data: bytes


@dataclass(frozen=True, slots=True)
class AcceptedAction:
    document: DocumentView
    job: IngestionJob


class DocumentAdminService:
    def __init__(
        self,
        *,
        database_url: str,
        clock: Clock,
        hmac_key: str,
        ingestion: IngestionService,
    ) -> None:
        self._database_url = database_url
        self._clock = clock
        self._hmac_key = hmac_key
        self._ingestion = ingestion

    async def list(self) -> list[DocumentView]:
        async with open_session(self._database_url) as session, UnitOfWork(session):
            views = await DocumentRepository(session).list_views()
        return views

    async def upload(
        self, *, admin_id: UUID, filename: str, data: bytes, title: str | None
    ) -> AcceptedAction:
        accepted, clean = _validated(filename, data, title)
        await self._count_upload(admin_id)
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = DocumentRepository(session)
            base = slugify(stem_of(accepted.filename) or clean)
            slug = numbered_slug(base, await repository.taken_slugs(base))
            document_id = await repository.create_document(
                slug=slug, title=clean, created_by=admin_id
            )
            job = await self._open(
                session, document_id, slug, clean, accepted, data, admin_id, DocumentAction.UPLOAD
            )
            view = await repository.view(document_id)
        return _accepted(view, job)

    async def replace(
        self, *, admin_id: UUID, document_id: UUID, filename: str, data: bytes
    ) -> AcceptedAction:
        accepted, _ = _validated(filename, data, None)
        await self._count_upload(admin_id)
        async with open_session(self._database_url) as session, UnitOfWork(session):
            slug, title = await self._lock_for_new_version(session, document_id)
            job = await self._open(
                session,
                document_id,
                slug,
                title,
                accepted,
                data,
                admin_id,
                DocumentAction.REPLACE,
            )
            view = await DocumentRepository(session).view(document_id)
        return _accepted(view, job)

    async def retry(self, *, admin_id: UUID, document_id: UUID) -> AcceptedAction:
        """Reprocessa os bytes da última versão com falha numa versão nova."""
        await self._count_upload(admin_id)
        async with open_session(self._database_url) as session, UnitOfWork(session):
            slug, title = await self._lock_for_new_version(session, document_id)
            stored = await DocumentRepository(session).latest_stored(document_id)
            if stored is None or stored.ingestion_status != "failed":
                raise Conflict(NOTHING_TO_RETRY)
            job = await self._open(
                session,
                document_id,
                slug,
                title,
                AcceptedFile(filename=stored.filename, media_type=stored.media_type),
                stored.original_bytes,
                admin_id,
                DocumentAction.RETRY,
            )
            view = await DocumentRepository(session).view(document_id)
        return _accepted(view, job)

    async def archive(self, *, admin_id: UUID, document_id: UUID) -> DocumentView:
        """Tira o documento da busca (FR-12). Arquivar de novo não grava outro evento."""
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = DocumentRepository(session)
            locked = await repository.lock(document_id)
            if locked is None:
                raise NotFound(DOCUMENT_NOT_FOUND)
            if locked[2] != "archived":
                await repository.archive(document_id)
                await AuditRepository(session).record(
                    actor_user_id=admin_id,
                    action=DocumentAction.ARCHIVE.value,
                    target_type=TARGET_TYPE,
                    target_id=document_id,
                    created_at=self._clock.now(),
                )
            view = await repository.view(document_id)
        if view is None:
            raise NotFound(DOCUMENT_NOT_FOUND)
        return view

    async def process(self, job: IngestionJob) -> str:
        """Passos 2 a 6 da seção 7.3. Uma falha marca só a versão nova como failed."""
        return await self._ingestion.process_version(
            version_id=job.version_id,
            slug=job.slug,
            title=job.title,
            media_type=job.media_type,
            data=job.data,
        )

    async def _lock_for_new_version(
        self, session: AsyncSession, document_id: UUID
    ) -> tuple[str, str]:
        repository = DocumentRepository(session)
        locked = await repository.lock(document_id)
        if locked is None:
            raise NotFound(DOCUMENT_NOT_FOUND)
        slug, title, status = locked
        if status == "archived":
            raise Conflict(DOCUMENT_ARCHIVED)
        now = self._clock.now()
        started = await repository.processing_since(document_id)
        if any(processing_is_recent(moment, now) for moment in started):
            raise Conflict(STILL_PROCESSING)
        return slug, title

    async def _count_upload(self, admin_id: UUID) -> None:
        """Balde de 30 por hora por admin. Conta a tentativa, mesmo que ela falhe depois."""
        if not self._hmac_key:
            raise RuntimeError("RATE_LIMIT_HMAC_KEY vazio.")
        now = self._clock.now()
        window = upload_window_start(now)
        key = bucket_key(
            purpose=UPLOAD_PURPOSE,
            subject=str(admin_id),
            day=now.astimezone(UTC).date(),
            key=self._hmac_key,
        )
        async with open_session(self._database_url) as session, UnitOfWork(session):
            count = await RateLimitRepository(session).increment(key, window)
        decision = upload_rate_decision(count=count, now=now, window_start=window)
        if decision.limited:
            raise RateLimited(UPLOADS_LIMITED, retry_after_seconds=decision.retry_after_seconds)

    async def _open(
        self,
        session: AsyncSession,
        document_id: UUID,
        slug: str,
        title: str,
        accepted: AcceptedFile,
        data: bytes,
        admin_id: UUID,
        action: DocumentAction,
    ) -> IngestionJob:
        repository = DocumentRepository(session)
        number = await repository.next_version(document_id)
        version_id = await repository.insert_version(
            document_id=document_id,
            version=number,
            filename=accepted.filename,
            media_type=accepted.media_type,
            sha256=hashlib.sha256(data).hexdigest(),
            original_bytes=data,
        )
        await repository.touch(document_id)
        await AuditRepository(session).record(
            actor_user_id=admin_id,
            action=action.value,
            target_type=TARGET_TYPE,
            target_id=document_id,
            created_at=self._clock.now(),
        )
        return IngestionJob(
            version_id=version_id,
            slug=slug,
            title=title,
            media_type=accepted.media_type,
            data=data,
        )


def _validated(filename: str, data: bytes, title: str | None) -> tuple[AcceptedFile, str]:
    """Tamanho, tipo e título conferidos no servidor (FR-10, NFR-10)."""
    errors: dict[str, str] = {}
    checked = check_file(filename, data)
    if isinstance(checked, UploadIssue):
        errors["file"] = issue_message(checked)
    clean = clean_title(title, filename)
    if isinstance(clean, UploadIssue):
        errors["title"] = issue_message(clean)
    if errors or isinstance(checked, UploadIssue) or isinstance(clean, UploadIssue):
        raise ValidationFailed(UPLOAD_INVALID, field_errors=errors)
    return checked, clean


def _accepted(view: DocumentView | None, job: IngestionJob) -> AcceptedAction:
    if view is None:
        raise NotFound(DOCUMENT_NOT_FOUND)
    return AcceptedAction(document=view, job=job)
