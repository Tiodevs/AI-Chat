"""Fila de pedidos de titular do admin. Seções 11.5, 12 e 15.5 do SDD (FR-16).

Camada de controle. As duas rotas chamam `require_admin` na primeira linha e então o
`PrivacyQueueService` de `get_privacy_queue_service`. A abertura do pedido pelo titular fica
em `privacy.py`.

A docstring de cada rota é a `description` da operação no OpenAPI (seção 6.6); a explicação
a mais fica em comentários, para não mudar o contrato.
"""

from typing import TYPE_CHECKING, Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.controllers.admin_guard import require_admin
from app.core.config import Settings
from app.core.container import get_clock, get_privacy_queue_service, get_settings
from app.ports.clock import Clock
from app.schemas.errors import ErrorResponse
from app.schemas.privacy import (
    PrivacyQueueItemResponse,
    PrivacyQueueResponse,
    PrivacyRequestUpdate,
)

if TYPE_CHECKING:
    from app.services.privacy import QueueItem

router = APIRouter()

# Status de erro documentados no OpenAPI, todos com o envelope `ErrorResponse`.
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


def _item(item: "QueueItem") -> PrivacyQueueItemResponse:
    """Converte o item da fila no schema, lendo os atributos do objeto (`from_attributes`)."""
    return PrivacyQueueItemResponse.model_validate(item, from_attributes=True)


@router.get(
    "/v1/admin/privacy/requests",
    operation_id="listPrivacyRequests",
    responses=_ERRORS,
)
async def list_privacy_requests(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
    service: Annotated[Any, Depends(get_privacy_queue_service)],
) -> PrivacyQueueResponse:
    """Pedidos abertos com os atrasados primeiro, e depois os 50 fechados mais recentes."""
    # Cada item diz se está atrasado (`overdue`) em relação a `generated_at` (seção 12).
    await require_admin(request, settings, clock)
    queue = await service.queue()
    return PrivacyQueueResponse(
        generated_at=queue.generated_at,
        requests=[_item(item) for item in queue.requests],
    )


@router.patch(
    "/v1/admin/privacy/requests/{request_id}",
    operation_id="updatePrivacyRequest",
    responses=_ERRORS,
)
async def update_privacy_request(
    request_id: UUID,
    body: PrivacyRequestUpdate,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
    service: Annotated[Any, Depends(get_privacy_queue_service)],
) -> PrivacyQueueItemResponse:
    """Muda o status e a nota de resolução. Grava `dsr.update`."""
    # `request_id` é o id do pedido de titular, não o `request_id` do log. Pedido inexistente
    # responde 404, e pedido fechado, 409. Status desconhecido, nota longa ou fechamento sem
    # nota voltam em `field_errors` com 422; um corpo fora dos limites do schema, 422 sem
    # `field_errors` (seção 12). Repetir o mesmo status e a mesma nota não grava evento.
    admin = await require_admin(request, settings, clock)
    item = await service.update(
        admin_id=admin.id,
        request_id=request_id,
        status=body.status,
        resolution_note=body.resolution_note,
    )
    return _item(item)
