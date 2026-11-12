"""Rotas do atendimento humano pelo lado do visitante. Seções 29.4 a 29.6 e 29.10 do SDD.

Camada de controle. Todas as rotas recebem o `HandoffService` de
`core/container.py:get_handoff_service`, que não tem provedor de IA (FR-21). O dono da
conversa vem dos dois cookies, como nas perguntas: `atrium_session` ou `atrium_guest`. Os
`POST` passam pela conferência de `Origin` do `ApiGuardMiddleware`, e as respostas saem com
`Cache-Control: no-store` (NFR-11). A docstring de cada rota é a `description` do OpenAPI.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse

from app.controllers.event_stream import event_stream_response, refuse_cross_site
from app.core.client_ip import client_ip
from app.core.container import get_handoff_service
from app.domain.auth import SESSION_COOKIE_NAME
from app.domain.questions import GUEST_COOKIE_NAME
from app.schemas.errors import ErrorResponse
from app.schemas.handoff import (
    AvailabilityResponse,
    HandoffMessageResponse,
    HandoffRequest,
    HandoffResponse,
    VisitorMessageRequest,
)

router = APIRouter()

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


@router.get("/v1/handoff/availability", operation_id="getHandoffAvailability")
async def get_availability(
    service: Annotated[Any, Depends(get_handoff_service)],
) -> AvailabilityResponse:
    """Se há alguém da equipe para atender: open, busy, closed ou disabled."""
    # Um status só, sem dizer quantas pessoas estão presentes (seção 29.4).
    return AvailabilityResponse(status=(await service.availability()).value)


@router.post(
    "/v1/conversations/{conversation_id}/handoff",
    operation_id="requestHandoff",
    status_code=201,
    responses={200: {"model": HandoffResponse}, **_ERRORS},
)
async def request_handoff(
    conversation_id: UUID,
    body: HandoffRequest,
    request: Request,
    response: Response,
    service: Annotated[Any, Depends(get_handoff_service)],
) -> HandoffResponse:
    """Chama a equipe depois de uma resposta que não ajudou. 201, ou 200 se já existe."""
    # As conferências e os erros seguem a ordem da seção 29.5, passo 1.
    view, created = await service.request(
        conversation_id,
        trigger_message_id=body.trigger_message_id,
        session_secret=request.cookies.get(SESSION_COOKIE_NAME),
        guest_secret=request.cookies.get(GUEST_COOKIE_NAME),
        client_ip=_ip(request),
    )
    if not created:
        response.status_code = 200
    return _handoff(view)


@router.get(
    "/v1/conversations/{conversation_id}/handoff",
    operation_id="getHandoff",
    responses=_ERRORS,
)
async def get_handoff(
    conversation_id: UUID,
    request: Request,
    service: Annotated[Any, Depends(get_handoff_service)],
) -> HandoffResponse:
    """O atendimento ativo ou o último da conversa. Sem nenhum, 404."""
    view = await service.current(
        conversation_id,
        session_secret=request.cookies.get(SESSION_COOKIE_NAME),
        guest_secret=request.cookies.get(GUEST_COOKIE_NAME),
    )
    return _handoff(view)


@router.post(
    "/v1/conversations/{conversation_id}/handoff/messages",
    operation_id="sendHandoffMessage",
    status_code=201,
    responses=_ERRORS,
)
async def send_message(
    conversation_id: UUID,
    body: VisitorMessageRequest,
    request: Request,
    service: Annotated[Any, Depends(get_handoff_service)],
) -> HandoffMessageResponse:
    """Mensagem do visitante para a equipe. Volta já sem os identificadores removidos."""
    # E-mail, CPF, cartão, telefone e número longo saem antes de gravar (seção 29.9.7). Um
    # reenvio do mesmo `client_message_id` responde 409 com `message_id`.
    stored = await service.send(
        conversation_id,
        text=body.text,
        client_message_id=body.client_message_id,
        session_secret=request.cookies.get(SESSION_COOKIE_NAME),
        guest_secret=request.cookies.get(GUEST_COOKIE_NAME),
    )
    return message_response(stored)


@router.post(
    "/v1/conversations/{conversation_id}/handoff/end",
    operation_id="endHandoff",
    responses=_ERRORS,
)
async def end_handoff(
    conversation_id: UUID,
    request: Request,
    service: Annotated[Any, Depends(get_handoff_service)],
) -> HandoffResponse:
    """Sai da fila ou encerra o atendimento. Repetir devolve o mesmo."""
    view = await service.end(
        conversation_id,
        session_secret=request.cookies.get(SESSION_COOKIE_NAME),
        guest_secret=request.cookies.get(GUEST_COOKIE_NAME),
    )
    return _handoff(view)


@router.get(
    "/v1/conversations/{conversation_id}/handoff/events",
    operation_id="handoffEvents",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "Eventos ready, message, status, reconnect e error.",
        },
        **_ERRORS,
    },
)
async def handoff_events(
    conversation_id: UUID,
    request: Request,
    service: Annotated[Any, Depends(get_handoff_service)],
) -> StreamingResponse:
    """Fluxo do atendimento para o dono da conversa, com Last-Event-ID opcional."""
    # Tudo o que pode falhar roda antes do primeiro byte e sai como JSON. O fluxo termina
    # aos 10 minutos com `reconnect` (seção 29.6).
    refuse_cross_site(request)
    stream = await service.open_stream(
        conversation_id,
        session_secret=request.cookies.get(SESSION_COOKIE_NAME),
        guest_secret=request.cookies.get(GUEST_COOKIE_NAME),
        last_event_id=request.headers.get("last-event-id"),
    )
    return event_stream_response(request, stream.events)


def message_response(stored: Any) -> HandoffMessageResponse:
    """A mensagem gravada no schema da resposta, sem quem da equipe escreveu."""
    return HandoffMessageResponse(
        id=stored.id,
        seq=stored.seq,
        role="attendant" if stored.role == "attendant" else "user",
        content=stored.content,
        redaction=stored.redaction,
        created_at=stored.created_at,
    )


def _handoff(view: Any) -> HandoffResponse:
    """O `HandoffView` do serviço no schema da resposta."""
    return HandoffResponse(
        id=view.id,
        status=view.status,
        queue_position=view.queue_position,
        close_reason=view.close_reason,
        requested_at=view.requested_at,
        assigned_at=view.assigned_at,
        closed_at=view.closed_at,
        seq=view.seq,
    )


def _ip(request: Request) -> str:
    """IP do cliente para os baldes do pedido (`app.core.client_ip`)."""
    return client_ip(
        request.headers.get("x-forwarded-for"),
        None if request.client is None else request.client.host,
    )
