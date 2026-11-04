"""Visão geral, qualidade e inspetor do admin. Seções 11.8, 12 e 15.5 do SDD."""

from typing import TYPE_CHECKING, Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from app.controllers.admin_guard import require_admin
from app.core.config import Settings
from app.core.container import get_clock, get_insights_service, get_settings
from app.domain.insights import DEFAULT_PERIOD_DAYS
from app.ports.clock import Clock
from app.schemas.errors import ErrorResponse
from app.schemas.insights import (
    BudgetResponse,
    ConversationSummaryResponse,
    FunnelRowResponse,
    IdentityResponse,
    InspectionResponse,
    InspectorMessageResponse,
    MetricResponse,
    OverviewResponse,
    QualityResponse,
    RevealRequest,
    TrendPointResponse,
)

if TYPE_CHECKING:
    from app.services.insights import Metric

router = APIRouter()

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


def _metric(metric: "Metric") -> MetricResponse:
    return MetricResponse(current=metric.current, previous=metric.previous)


@router.get("/v1/admin/overview", operation_id="adminOverview", responses=_ERRORS)
async def admin_overview(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
    service: Annotated[Any, Depends(get_insights_service)],
    period_days: Annotated[int, Query()] = DEFAULT_PERIOD_DAYS,
) -> OverviewResponse:
    """Indicadores do período contra o período anterior, tendência, desfechos, funil e orçamento."""
    await require_admin(request, settings, clock)
    overview = await service.overview(period_days)
    return OverviewResponse(
        period_days=overview.period_days,
        generated_at=overview.generated_at,
        questions=_metric(overview.questions),
        answer_rate=_metric(overview.answer_rate),
        abstention_rate=_metric(overview.abstention_rate),
        helpful_rate=_metric(overview.helpful_rate),
        trend=[
            TrendPointResponse(date=point.day, questions=point.questions, answered=point.answered)
            for point in overview.trend
        ],
        outcomes=overview.outcomes,
        intents=overview.intents,
        feedback=overview.feedback,
        funnel=[
            FunnelRowResponse(step=row.step, chat=row.chat, form=row.form)
            for row in overview.funnel
        ],
        budget=BudgetResponse(
            used_tokens=overview.budget.used_tokens,
            daily_budget=overview.budget.daily_budget,
            ratio=overview.budget.ratio,
        ),
    )


@router.get("/v1/admin/quality", operation_id="adminQuality", responses=_ERRORS)
async def admin_quality(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
    service: Annotated[Any, Depends(get_insights_service)],
    period_days: Annotated[int, Query()] = DEFAULT_PERIOD_DAYS,
    outcome: Annotated[str | None, Query(max_length=40)] = None,
    feedback: Annotated[str | None, Query(max_length=40)] = None,
) -> QualityResponse:
    """Contagens por desfecho e feedback e as conversas recentes, pseudonimizadas."""
    await require_admin(request, settings, clock)
    quality = await service.quality(period_days=period_days, outcome=outcome, feedback=feedback)
    return QualityResponse(
        period_days=quality.period_days,
        outcomes=quality.outcomes,
        feedback=quality.feedback,
        conversations=[
            ConversationSummaryResponse.model_validate(item, from_attributes=True)
            for item in quality.conversations
        ],
    )


@router.get(
    "/v1/admin/conversations/{conversation_id}",
    operation_id="adminConversation",
    responses=_ERRORS,
)
async def admin_conversation(
    conversation_id: UUID,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
    service: Annotated[Any, Depends(get_insights_service)],
) -> InspectionResponse:
    """Conversa pseudonimizada com os links de rastro. Grava `conversation.view`."""
    admin = await require_admin(request, settings, clock)
    inspection = await service.inspect(admin_id=admin.id, conversation_id=conversation_id)
    return InspectionResponse(
        id=inspection.id,
        subject_kind=inspection.subject_kind,
        pseudonym=inspection.pseudonym,
        created_at=inspection.created_at,
        messages=[
            InspectorMessageResponse.model_validate(item, from_attributes=True)
            for item in inspection.messages
        ],
    )


@router.post(
    "/v1/admin/conversations/{conversation_id}/reveal",
    operation_id="revealIdentity",
    responses=_ERRORS,
)
async def reveal_identity(
    conversation_id: UUID,
    body: RevealRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
    service: Annotated[Any, Depends(get_insights_service)],
) -> IdentityResponse:
    """Devolve a identidade do membro. Exige motivo e grava `identity.reveal`."""
    admin = await require_admin(request, settings, clock)
    identity = await service.reveal(
        admin_id=admin.id, conversation_id=conversation_id, reason=body.reason
    )
    return IdentityResponse(
        conversation_id=identity.conversation_id,
        full_name=identity.full_name,
        email=identity.email,
    )
