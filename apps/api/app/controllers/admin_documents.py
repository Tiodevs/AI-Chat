"""Gestão de documentos pelo admin. Seções 7.3, 10.4, 12 e 15.5 do SDD.

O upload grava a versão em `processing` e responde logo. A ingestão roda numa tarefa de
fundo depois da resposta.

Camada de controle. Toda rota chama `require_admin` na primeira linha e então o
`DocumentAdminService` de `get_document_admin_service`. O FastAPI já leu o corpo multipart
quando a rota começa (`File()` e `Form()`), então um upload sem sessão chega inteiro antes do
401; a Etapa 15.2 inverte essa ordem. Upload, substituição e nova tentativa contam no balde
de 30 por hora por admin (seção 10.4).

A docstring de cada rota é a `description` da operação no OpenAPI (seção 6.6); a explicação
a mais fica em comentários, para não mudar o contrato.
"""

from typing import TYPE_CHECKING, Annotated, Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Request, UploadFile

from app.controllers.admin_guard import require_admin
from app.core.config import Settings
from app.core.container import get_clock, get_document_admin_service, get_settings
from app.domain.documents import MAX_UPLOAD_BYTES
from app.ports.clock import Clock
from app.schemas.documents import DocumentListResponse, DocumentResponse, document_response
from app.schemas.errors import ErrorResponse

if TYPE_CHECKING:
    from app.services.documents import AcceptedAction, DocumentAdminService

router = APIRouter()

# Status de erro documentados no OpenAPI, todos com o envelope `ErrorResponse`.
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
}


async def _read_limited(upload: UploadFile) -> bytes:
    """Lê no máximo 10 MB mais um byte. O serviço recusa o que passar do limite.

    O byte a mais mostra que o arquivo passou do limite sem trazer o resto para a memória.
    O `UploadFile` já está guardado num arquivo temporário pelo leitor do multipart.
    """
    return await upload.read(MAX_UPLOAD_BYTES + 1)


def _schedule(
    tasks: BackgroundTasks, service: "DocumentAdminService", accepted: "AcceptedAction"
) -> DocumentResponse:
    """Agenda `service.process` como tarefa de fundo e devolve o documento.

    O Starlette roda a tarefa no mesmo processo, depois de enviar a resposta (seção 7.3). O
    pedido só termina para o `RequestIdMiddleware` quando a ingestão acaba, então a duração
    medida da rota inclui a ingestão.
    """
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
    # Ativos primeiro, depois os arquivados, do mais recente ao mais antigo (seção 12).
    await require_admin(request, settings, clock)
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
    # Responde 201 com a versão nova em `processing` e `active_version` nula. O tipo vem da
    # extensão do nome, e o título, quando vazio, do nome do arquivo (seção 12). Arquivo
    # inválido ou título acima de 200 caracteres responde 422 com `field_errors`. Um título
    # acima de 400 caracteres já cai no `Form(max_length=400)`: 422 sem `field_errors`.
    admin = await require_admin(request, settings, clock)
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
    # Responde 202 e grava `document.replace`. Documento inexistente, 404; arquivado ou com
    # uma versão em `processing` há menos de 15 minutos, 409 (seção 7.3).
    admin = await require_admin(request, settings, clock)
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
    # Sem corpo. Responde 202 e grava `document.retry`. Sem falha na última versão, 409, além
    # dos casos de `replace_document`.
    admin = await require_admin(request, settings, clock)
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
    # Responde 200 com o documento. Arquivar de novo não grava outro evento (seção 12).
    admin = await require_admin(request, settings, clock)
    view = await service.archive(admin_id=admin.id, document_id=document_id)
    return document_response(view)
