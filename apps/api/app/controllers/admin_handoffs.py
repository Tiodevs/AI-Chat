"""Atendimentos encerrados para o admin. Seções 29.9.4, 29.10 e 29.11 do SDD (J11).

Camada de controle. A lista não tem conteúdo; o conteúdo de um encerrado só abre com um
motivo de 10 a 500 caracteres, gravado em `handoff.view` na mesma transação (FR-26). Um
`attendant` recebe 403 aqui, como em todo `/v1/admin` (seção 29.3). A docstring de cada rota
é a `description` da operação no OpenAPI.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from app.controllers.admin_guard import require_admin
from app.controllers.attendance import handoff_detail
from app.core.config import Settings
from app.core.container import get_attendance_service, get_clock, get_settings
from app.domain.handoff import StaffMember
from app.ports.clock import Clock
from app.schemas.errors import ErrorResponse
from app.schemas.handoff import (
    ClosedHandoffListResponse,
    ClosedHandoffResponse,
    HandoffDetailResponse,
    ViewRequest,
)

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


async def require_admin_staff(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> StaffMember:
    """O admin da sessão como pessoa da equipe: 401 sem sessão, 403 para outro papel."""
    profile = await require_admin(request, settings, clock)
    return StaffMember(user_id=profile.id, role=profile.role)


router = APIRouter(dependencies=[Depends(require_admin_staff)])

Admin = Annotated[StaffMember, Depends(require_admin_staff)]
Service = Annotated[Any, Depends(get_attendance_service)]


@router.get("/v1/admin/handoffs", operation_id="listClosedHandoffs", responses=_ERRORS)
async def list_closed(
    service: Service,
    period_days: Annotated[int, Query()] = 7,
) -> ClosedHandoffListResponse:
    """Até 100 atendimentos encerrados no período, 7 ou 30 dias, sem conteúdo."""
    rows = await service.closed_list(period_days)
    return ClosedHandoffListResponse(
        handoffs=[
            ClosedHandoffResponse(
                id=row.handoff.id,
                label=row.handoff.label,
                trigger=row.handoff.trigger,
                requested_at=row.handoff.requested_at,
                assigned_at=row.handoff.assigned_at,
                closed_at=row.handoff.closed_at,
                close_reason=row.handoff.close_reason,
                message_count=row.message_count,
                content_purged=row.handoff.content_purged,
            )
            for row in rows
        ]
    )


@router.post(
    "/v1/admin/handoffs/{handoff_id}/view",
    operation_id="viewClosedHandoff",
    responses=_ERRORS,
)
async def view_closed(
    handoff_id: UUID, body: ViewRequest, admin: Admin, service: Service
) -> HandoffDetailResponse:
    """Abre um encerrado com o motivo, gravado em handoff.view. Ativo, 409."""
    return handoff_detail(await service.view_closed(admin, handoff_id, body.reason))
