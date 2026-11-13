"""Rotas do console de atendimento, para `attendant` e `admin`. Seções 29.3, 29.6 e 29.10.

Camada de controle. `require_attendant` é uma dependência do roteador: roda antes da rota e
responde 401 sem sessão e 403 para um `member` (seção 29.3). As rotas recebem o
`AttendanceService` de `core/container.py:get_attendance_service`, sem provedor de IA. O
conteúdo de um atendimento só sai para quem o assumiu; para outra pessoa, 404 (NFR-18). A
docstring de cada rota é a `description` da operação no OpenAPI.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from app.adapters.password_hasher import get_password_hasher
from app.controllers.event_stream import event_stream_response, refuse_cross_site
from app.controllers.handoff import message_response
from app.core.config import Settings
from app.core.container import get_attendance_service, get_clock, get_settings
from app.domain.auth import SESSION_COOKIE_NAME, STAFF_ROLES
from app.domain.errors import Forbidden
from app.domain.handoff import StaffMember
from app.ports.clock import Clock
from app.prompts.handoff import STAFF_ONLY
from app.schemas.errors import ErrorResponse
from app.schemas.handoff import (
    AcknowledgementRequest,
    AttendanceMeResponse,
    CloseRequest,
    ConversationLineResponse,
    HandoffDetailResponse,
    HandoffMessageResponse,
    PresenceRequest,
    QueueResponse,
    RedactRequest,
    StaffCitationResponse,
    StaffHandoffResponse,
    StaffMessageRequest,
)

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
}


async def require_attendant(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> StaffMember:
    """A pessoa da equipe da sessão: 401 sem sessão válida, 403 para quem não é da equipe.

    `attendant` e `admin` atendem (seção 29.3). Cada chamada lê a sessão numa transação
    curta, com o `AuthService` criado aqui, como em `admin_guard.py`.
    """
    from app.services.auth import AuthService

    profile = await AuthService(
        database_url=settings.database_url,
        clock=clock,
        hasher=get_password_hasher(),
        hmac_key=settings.rate_limit_hmac_key,
        app_env=settings.app_env,
    ).authenticate(request.cookies.get(SESSION_COOKIE_NAME))
    if profile.role not in STAFF_ROLES:
        raise Forbidden(STAFF_ONLY)
    return StaffMember(user_id=profile.id, role=profile.role)


router = APIRouter(dependencies=[Depends(require_attendant)])

Staff = Annotated[StaffMember, Depends(require_attendant)]
Service = Annotated[Any, Depends(get_attendance_service)]


@router.get("/v1/attendance/me", operation_id="getAttendanceMe", responses=_ERRORS)
async def attendance_me(staff: Staff, service: Service) -> AttendanceMeResponse:
    """A presença marcada, o aceite do compromisso e a versão vigente dele."""
    return _me(await service.me(staff))


@router.post(
    "/v1/attendance/acknowledgement",
    operation_id="acknowledgeAttendantTerms",
    responses=_ERRORS,
)
async def acknowledge(
    body: AcknowledgementRequest, staff: Staff, service: Service
) -> AttendanceMeResponse:
    """Aceita o compromisso de confidencialidade. Outra versão que não a vigente, 422."""
    return _me(await service.acknowledge(staff, body.version))


@router.put("/v1/attendance/presence", operation_id="setAttendancePresence", responses=_ERRORS)
async def set_presence(
    body: PresenceRequest, staff: Staff, service: Service
) -> AttendanceMeResponse:
    """Marca Disponível ou Ausente."""
    return _me(await service.set_presence(staff, body.status))


@router.get("/v1/attendance/queue", operation_id="getAttendanceQueue", responses=_ERRORS)
async def get_queue(staff: Staff, service: Service) -> QueueResponse:
    """A fila sem conteúdo, os atendimentos da pessoa e quantas pessoas estão disponíveis."""
    view = await service.queue(staff)
    return QueueResponse(
        queued=[staff_handoff(item) for item in view.queued],
        mine=[staff_handoff(item) for item in view.mine],
        available_attendants=view.available_attendants,
    )


@router.post(
    "/v1/attendance/handoffs/{handoff_id}/take",
    operation_id="takeHandoff",
    responses=_ERRORS,
)
async def take(handoff_id: UUID, staff: Staff, service: Service) -> HandoffDetailResponse:
    """Assume um atendimento da fila. Quem perde a corrida recebe 409 handoff_taken."""
    return handoff_detail(await service.take(staff, handoff_id))


@router.get(
    "/v1/attendance/handoffs/{handoff_id}",
    operation_id="getStaffHandoff",
    responses=_ERRORS,
)
async def get_detail(
    handoff_id: UUID,
    staff: Staff,
    service: Service,
    after_seq: Annotated[int | None, Query(ge=0)] = None,
) -> HandoffDetailResponse:
    """O atendimento e a conversa, só para quem assumiu. after_seq traz só o que é novo."""
    return handoff_detail(await service.detail(staff, handoff_id, after_seq=after_seq))


@router.post(
    "/v1/attendance/handoffs/{handoff_id}/messages",
    operation_id="sendStaffMessage",
    status_code=201,
    responses=_ERRORS,
)
async def send_message(
    handoff_id: UUID, body: StaffMessageRequest, staff: Staff, service: Service
) -> HandoffMessageResponse:
    """Responde ao visitante, ou manda a orientação de emergência com o modelo fixo."""
    stored = await service.send(
        staff,
        handoff_id,
        text=body.text,
        template=body.template,
        client_message_id=body.client_message_id,
    )
    return message_response(stored)


@router.post(
    "/v1/attendance/handoffs/{handoff_id}/release",
    operation_id="releaseHandoff",
    responses=_ERRORS,
)
async def release(handoff_id: UUID, staff: Staff, service: Service) -> StaffHandoffResponse:
    """Devolve o atendimento à fila."""
    return staff_handoff(await service.release(staff, handoff_id))


@router.post(
    "/v1/attendance/handoffs/{handoff_id}/close",
    operation_id="closeHandoff",
    responses=_ERRORS,
)
async def close(
    handoff_id: UUID, body: CloseRequest, staff: Staff, service: Service
) -> StaffHandoffResponse:
    """Encerra com um motivo da lista fechada."""
    return staff_handoff(await service.close(staff, handoff_id, body.reason))


@router.post(
    "/v1/attendance/handoffs/{handoff_id}/messages/{message_id}/redact",
    operation_id="redactHandoffMessage",
    responses=_ERRORS,
)
async def redact(
    handoff_id: UUID,
    message_id: UUID,
    body: RedactRequest,
    staff: Staff,
    service: Service,
) -> HandoffMessageResponse:
    """Troca o texto de uma mensagem do atendimento pelo marcador, com a categoria."""
    return message_response(await service.redact(staff, handoff_id, message_id, body.category))


@router.get(
    "/v1/attendance/events",
    operation_id="attendanceEvents",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "Eventos ready, queue, assigned, message, status, removed e reconnect.",
        },
        **_ERRORS,
    },
)
async def attendance_events(request: Request, staff: Staff, service: Service) -> StreamingResponse:
    """Fluxo do console: a fila sem conteúdo e as mensagens dos atendimentos da pessoa."""
    refuse_cross_site(request)
    stream = await service.open_console(staff, request.cookies.get(SESSION_COOKIE_NAME))
    return event_stream_response(request, stream.events)


def staff_handoff(item: Any) -> StaffHandoffResponse:
    """O `StaffHandoff` do serviço no schema, sem conteúdo nem dado do perfil."""
    return StaffHandoffResponse(
        handoff_id=item.id,
        label=item.label,
        status=item.status,
        trigger=item.trigger,
        requested_at=item.requested_at,
        queued_at=item.queued_at,
        assigned_at=item.assigned_at,
        closed_at=item.closed_at,
        close_reason=item.close_reason,
        returned=item.returned,
        visitor_present=item.visitor_present,
        seq=item.last_seq,
        channel="whatsapp" if item.channel == "whatsapp" else "web",
    )


def handoff_detail(detail: Any) -> HandoffDetailResponse:
    """O atendimento e a conversa da seção 29.9.4 no schema da resposta."""
    return HandoffDetailResponse(
        handoff=staff_handoff(detail.handoff),
        conversation=[
            ConversationLineResponse(
                id=line.id,
                role="assistant" if line.role == "assistant" else "user",
                content=line.content,
                citations=[
                    StaffCitationResponse(
                        index=citation.index,
                        document_title=citation.document_title,
                        heading=citation.heading,
                    )
                    for citation in line.citations
                ],
                outcome=line.outcome,
                created_at=line.created_at,
            )
            for line in detail.conversation
        ],
        messages=[
            message_response(message, detail.deliveries.get(message.id))
            for message in detail.messages
        ],
    )


def _me(me: Any) -> AttendanceMeResponse:
    """O `AttendanceMe` do serviço no schema da resposta."""
    return AttendanceMeResponse(
        presence=me.presence, acknowledged=me.acknowledged, terms_version=me.terms_version
    )
