"""Fila de pedidos de titular do admin. Seções 11.5, 12 e 15.5 do SDD (FR-16)."""

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

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


def _item(item: "QueueItem") -> PrivacyQueueItemResponse:
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
    admin = await require_admin(request, settings, clock)
    item = await service.update(
        admin_id=admin.id,
        request_id=request_id,
        status=body.status,
        resolution_note=body.resolution_note,
    )
    return _item(item)
