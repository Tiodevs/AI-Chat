"""Visão geral, qualidade e inspetor do admin. Seções 11.8, 12 e 15.5 do SDD.

Camada de controle. Toda rota chama `require_admin` na primeira linha e então o
`InsightsService` de `get_insights_service`. Os números vêm do banco, não do Prometheus
(seção 18.3). O inspetor só mostra pseudônimos; nome e e-mail saem só por `reveal`, com
motivo e auditoria.

A docstring de cada rota é a `description` da operação no OpenAPI (seção 6.6); a explicação
a mais fica em comentários, para não mudar o contrato.
"""

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

# Status de erro documentados no OpenAPI, todos com o envelope `ErrorResponse`.
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


def _metric(metric: "Metric") -> MetricResponse:
    """Converte um indicador do serviço em `{current, previous}`; `null` sem denominador."""
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
    # `period_days` aceita 7 ou 30; outro valor responde 422 com `field_errors.period_days`. O
    # orçamento é o do dia UTC corrente.
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
    # `outcome` e `feedback` filtram as conversas; um valor desconhecido responde 422 com
    # `field_errors`, e um valor acima de 40 caracteres já cai na validação da query. A lista
    # só traz convidados e membros com `quality_improvement` vigente (seção 12).
    await require_admin(request, settings, clock)
    quality = await service.quality(period_days=period_days, outcome=outcome, feedback=feedback)
    return QualityResponse(
        period_days=quality.period_days,
        outcomes=quality.outcomes,
        feedback=quality.feedback,
        # `from_attributes` lê os campos direto do objeto do serviço, sem um dicionário no meio.
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
    # A auditoria vai na mesma transação da leitura. Conversa de membro sem
    # `quality_improvement` vigente responde 404 e não grava nada (seção 12).
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
    # O motivo precisa ter de 10 a 500 caracteres depois de juntar espaços; fora disso, 422 em
    # `field_errors.reason`. Conversa de convidado responde 409, e conversa fora do inspetor,
    # 404 (seção 12).
    admin = await require_admin(request, settings, clock)
    identity = await service.reveal(
        admin_id=admin.id, conversation_id=conversation_id, reason=body.reason
    )
    return IdentityResponse(
        conversation_id=identity.conversation_id,
        full_name=identity.full_name,
        email=identity.email,
    )
