"""Gestão de documentos pelo admin: listar, enviar, substituir, tentar de novo e arquivar.

Seções 7.3, 8.1, 10.4 e 12 do SDD. A versão nasce em `processing` na mesma transação que
grava a auditoria. A ingestão roda depois, fora do pedido, e só troca a versão ativa no
sucesso (FR-11).

Camada de serviço. `controllers/admin_documents.py` confere o admin com
`controllers/admin_guard.py:require_admin` e só então chama `DocumentAdminService`, montado
por pedido em `core/container.py:get_document_admin_service` com um `IngestionService`
próprio. O controlador agenda `process` como tarefa de fundo do FastAPI, que roda no mesmo
processo da API depois da resposta (a seção 6.5 a leva para uma fila quando houver réplicas).

Usa `DocumentRepository`, `AuditRepository` e `RateLimitRepository`, e as regras de upload,
slug e prazo de `domain/documents.py`. Auditoria: `document.upload`, `document.replace`,
`document.retry` e `document.archive`. Limite: 30 envios por hora por admin (seção 10.4).
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

# `target_type` dos eventos de auditoria de documento (seção 8.1).
TARGET_TYPE = "document"


@dataclass(frozen=True, slots=True)
class IngestionJob:
    """O que a tarefa de fundo precisa para os passos 2 a 6 da seção 7.3.

    Os bytes vão em memória, então a tarefa não relê o arquivo do banco.
    """

    version_id: UUID
    slug: str
    title: str
    media_type: str
    data: bytes


@dataclass(frozen=True, slots=True)
class AcceptedAction:
    """Resultado de enviar, substituir ou tentar de novo.

    `document` vira o corpo da resposta 201 ou 202. `job` vai para a tarefa de fundo.
    """

    document: DocumentView
    job: IngestionJob


class DocumentAdminService:
    """Ações do admin sobre o corpus. `admin_id` já vem conferido pelo controlador.

    `hmac_key` é a `RATE_LIMIT_HMAC_KEY` do balde de uploads.
    """

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
        """Ativos primeiro, depois os arquivados, do mais recente ao mais antigo.

        Cada item traz a versão ativa e a última versão, com o status de ingestão. Uma
        transação curta de leitura.
        """
        async with open_session(self._database_url) as session, UnitOfWork(session):
            views = await DocumentRepository(session).list_views()
        return views

    async def upload(
        self, *, admin_id: UUID, filename: str, data: bytes, title: str | None
    ) -> AcceptedAction:
        """Cria um documento com a primeira versão em `processing` e grava `document.upload`.

        1. Confere o arquivo e o título no servidor: tipo pela extensão e pelo conteúdo,
           tamanho até 10 MB, título até 200 caracteres. Falha responde 422.
        2. Conta a tentativa no balde de uploads (429 a partir da 31ª na hora).
        3. Numa transação: escolhe o slug pelo nome do arquivo (`-2`, `-3` quando já
           existe), cria o documento, grava a versão e a auditoria.

        A ingestão não roda aqui: o controlador agenda `process(job)`. A seção 12 diz que o
        balde conta a tentativa antes da validação do documento. Aqui o arquivo é conferido
        antes, então um arquivo inválido responde 422 sem gastar o balde.
        """
        # 1. Validação do arquivo, antes de qualquer transação.
        accepted, clean = _validated(filename, data, title)
        # 2. Balde de 30 por hora, numa transação própria.
        await self._count_upload(admin_id)
        # 3. Documento, versão e auditoria confirmam juntos.
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
        """Grava uma versão nova de um documento existente e `document.replace`.

        1. Confere o arquivo (422), como no envio. O título do documento não muda.
        2. Conta a tentativa no balde de uploads (429).
        3. Numa transação: trava a linha do documento, recusa um documento arquivado ou com
           versão em `processing` há menos de 15 minutos (409), e grava a versão e a
           auditoria.

        A versão ativa continua respondendo até a nova chegar a `ready` (FR-11). Erros:
        `NotFound` (404), `Conflict` (409), `ValidationFailed` (422), `RateLimited` (429).
        """
        # 1.
        accepted, _ = _validated(filename, data, None)
        # 2. A tentativa conta mesmo que a transação abaixo recuse a ação.
        await self._count_upload(admin_id)
        # 3. O `FOR UPDATE` serializa duas ações simultâneas no mesmo documento.
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
        """Reprocessa os bytes da última versão com falha numa versão nova.

        1. Conta a tentativa no balde de uploads (429). Não há arquivo para conferir.
        2. Numa transação: trava o documento, aplica as mesmas recusas da substituição (404 e
           409), exige que a última versão esteja `failed` (409 sem falha) e grava a versão
           nova com os bytes guardados, mais `document.retry`.
        """
        # 1.
        await self._count_upload(admin_id)
        # 2.
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
        """Tira o documento da busca (FR-12). Arquivar de novo não grava outro evento.

        Numa transação: trava o documento (404 se não existe), muda o status para
        `archived` e grava `document.archive` só quando ele ainda não estava arquivado. Um
        documento arquivado deixa de ser pesquisável pelo predicado da seção 8.2.
        """
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = DocumentRepository(session)
            locked = await repository.lock(document_id)
            if locked is None:
                raise NotFound(DOCUMENT_NOT_FOUND)
            # `locked` é (slug, título, status).
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
        """Passos 2 a 6 da seção 7.3. Uma falha marca só a versão nova como failed.

        Roda na tarefa de fundo, depois da resposta HTTP, e chama o embedding pela rede
        fora de transação. Devolve `"embedded"` ou `"failed"`.
        """
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
        """Trava o documento e confere se ele aceita uma versão nova.

        Roda dentro da transação de quem chama. Recusa um documento inexistente (404), um
        arquivado (409) e um com versão em `processing` há menos de 15 minutos (409): assim
        uma versão mais velha nunca termina depois da nova e toma o lugar dela (seção 7.3).
        Devolve o slug e o título.
        """
        repository = DocumentRepository(session)
        locked = await repository.lock(document_id)
        if locked is None:
            raise NotFound(DOCUMENT_NOT_FOUND)
        slug, title, status = locked
        if status == "archived":
            raise Conflict(DOCUMENT_ARCHIVED)
        now = self._clock.now()
        started = await repository.processing_since(document_id)
        # Depois de 15 minutos a versão conta como presa, e uma nova pode entrar.
        if any(processing_is_recent(moment, now) for moment in started):
            raise Conflict(STILL_PROCESSING)
        return slug, title

    async def _count_upload(self, admin_id: UUID) -> None:
        """Balde de 30 por hora por admin. Conta a tentativa, mesmo que ela falhe depois.

        A transação do contador confirma antes da ação, então um 404 ou 409 seguinte não
        devolve a tentativa. A chave é o HMAC do id do admin com o sal do dia. Erros:
        `RateLimited` (429), e `RuntimeError` sem `RATE_LIMIT_HMAC_KEY`.
        """
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
        """Grava a versão seguinte em `processing` e o evento de auditoria da ação.

        Roda na transação de quem chama, com o documento já travado ou recém-criado. Guarda
        o SHA-256 e os bytes originais, que a nova tentativa reaproveita, e atualiza o
        `updated_at` do documento. Devolve o trabalho da tarefa de fundo.
        """
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
    """Tamanho, tipo e título conferidos no servidor (FR-10, NFR-10).

    O tipo vem da extensão e é conferido no conteúdo, nunca no tipo declarado pelo
    navegador. Junta os erros de `file` e `title` num só `ValidationFailed` (422). Devolve o
    arquivo aceito e o título limpo, que sem título enviado é o nome do arquivo.
    """
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
    """Junta a visão do documento ao trabalho. Sem visão, o documento sumiu: 404."""
    if view is None:
        raise NotFound(DOCUMENT_NOT_FOUND)
    return AcceptedAction(document=view, job=job)
