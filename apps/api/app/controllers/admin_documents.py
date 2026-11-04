"""Gestão de documentos pelo admin. Seções 7.3, 10.4, 12 e 15.5 do SDD.

O upload grava a versão em `processing` e responde logo. A ingestão roda numa tarefa de
fundo depois da resposta.
"""

from typing import TYPE_CHECKING, Annotated, Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Request, UploadFile

from app.adapters.password_hasher import get_password_hasher
from app.core.config import Settings
from app.core.container import get_clock, get_document_admin_service, get_settings
from app.domain.auth import SESSION_COOKIE_NAME
from app.domain.documents import MAX_UPLOAD_BYTES
from app.domain.profile import Profile
from app.ports.clock import Clock
from app.schemas.documents import DocumentListResponse, DocumentResponse, document_response
from app.schemas.errors import ErrorResponse

if TYPE_CHECKING:
    from app.services.documents import AcceptedAction, DocumentAdminService

router = APIRouter()

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
}


async def _admin(request: Request, settings: Settings, clock: Clock) -> Profile:
    from app.services.auth import AuthService

    return await AuthService(
        database_url=settings.database_url,
        clock=clock,
        hasher=get_password_hasher(),
        hmac_key=settings.rate_limit_hmac_key,
        app_env=settings.app_env,
    ).require_admin(request.cookies.get(SESSION_COOKIE_NAME))


async def _read_limited(upload: UploadFile) -> bytes:
    """Lê no máximo 10 MB mais um byte. O serviço recusa o que passar do limite."""
    return await upload.read(MAX_UPLOAD_BYTES + 1)


def _schedule(
    tasks: BackgroundTasks, service: "DocumentAdminService", accepted: "AcceptedAction"
) -> DocumentResponse:
    tasks.add_task(service.process, accepted.job)
    return document_response(accepted.document)


@router.get("/v1/admin/documents", operation_id="listDocuments", responses=_ERRORS)
async def list_documents(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
    service: Annotated[Any, Depends(get_document_admin_service)],
) -> DocumentListResponse:
    """Documentos, versão ativa e a última versão com o status de ingestão."""
    await _admin(request, settings, clock)
    views = await service.list()
    return DocumentListResponse(documents=[document_response(view) for view in views])


@router.post(
    "/v1/admin/documents",
    operation_id="uploadDocument",
    status_code=201,
    responses=_ERRORS,
)
async def upload_document(
    request: Request,
    tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
    service: Annotated[Any, Depends(get_document_admin_service)],
    title: Annotated[str | None, Form(max_length=400)] = None,
) -> DocumentResponse:
    """Markdown, texto ou PDF de até 10 MB. Grava `document.upload` e começa a ingestão."""
    admin = await _admin(request, settings, clock)
    accepted = await service.upload(
        admin_id=admin.id,
        filename=file.filename or "",
        data=await _read_limited(file),
        title=title,
    )
    return _schedule(tasks, service, accepted)


@router.post(
    "/v1/admin/documents/{document_id}/replace",
    operation_id="replaceDocument",
    status_code=202,
    responses=_ERRORS,
)
async def replace_document(
    document_id: UUID,
    request: Request,
    tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
    service: Annotated[Any, Depends(get_document_admin_service)],
) -> DocumentResponse:
    """Versão nova. A anterior segue ativa até a nova chegar a `ready` (FR-11)."""
    admin = await _admin(request, settings, clock)
    accepted = await service.replace(
        admin_id=admin.id,
        document_id=document_id,
        filename=file.filename or "",
        data=await _read_limited(file),
    )
    return _schedule(tasks, service, accepted)


@router.post(
    "/v1/admin/documents/{document_id}/retry",
    operation_id="retryDocument",
    status_code=202,
    responses=_ERRORS,
)
async def retry_document(
    document_id: UUID,
    request: Request,
    tasks: BackgroundTasks,
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
    service: Annotated[Any, Depends(get_document_admin_service)],
) -> DocumentResponse:
    """Reprocessa o arquivo da última versão com falha numa versão nova."""
    admin = await _admin(request, settings, clock)
    accepted = await service.retry(admin_id=admin.id, document_id=document_id)
    return _schedule(tasks, service, accepted)


@router.post(
    "/v1/admin/documents/{document_id}/archive",
    operation_id="archiveDocument",
    responses=_ERRORS,
)
async def archive_document(
    document_id: UUID,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
    service: Annotated[Any, Depends(get_document_admin_service)],
) -> DocumentResponse:
    """Tira o documento das respostas (FR-12) e grava `document.archive`."""
    admin = await _admin(request, settings, clock)
    view = await service.archive(admin_id=admin.id, document_id=document_id)
    return document_response(view)
