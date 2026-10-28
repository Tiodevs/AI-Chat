"""Conversas, fluxo SSE e o diagnóstico do rewrite. Seções 7.1 e 12."""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import Response, StreamingResponse

from app.core.client_ip import client_ip
from app.core.container import get_conversation_service
from app.core.context import current_request_id
from app.core.cookies import apply_session_cookie
from app.core.sse import (
    DIAGNOSTIC_TICK_INTERVAL_SECONDS,
    format_comment,
    format_event,
    iter_diagnostic_indexes,
)
from app.domain.auth import SESSION_COOKIE_NAME
from app.domain.questions import GUEST_COOKIE_NAME
from app.schemas.conversations import (
    AskRequest,
    CitationResponse,
    ConversationCreatedResponse,
    ConversationListResponse,
    ConversationResponse,
    ConversationSummaryResponse,
    FeedbackRequest,
    FeedbackResponse,
    MessageResponse,
)
from app.schemas.errors import ErrorResponse
from app.services.conversation_events import (
    AskEvent,
    CitationEvent,
    CommentEvent,
    DoneEvent,
    ErrorEvent,
    MetaEvent,
    ReplaceEvent,
    TokenEvent,
)

router = APIRouter()

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
}


@router.post(
    "/v1/conversations",
    operation_id="createConversation",
    status_code=201,
    responses=_ERRORS,
)
async def create_conversation(
    request: Request,
    response: Response,
    service: Annotated[Any, Depends(get_conversation_service)],
) -> ConversationCreatedResponse:
    """Cria uma conversa da sessão ou da chave de convidado."""
    record, cookie = await service.create(
        session_secret=request.cookies.get(SESSION_COOKIE_NAME),
        guest_secret=request.cookies.get(GUEST_COOKIE_NAME),
    )
    if cookie is not None:
        apply_session_cookie(response, cookie)
    return ConversationCreatedResponse(id=record.id, created_at=record.created_at)


@router.get(
    "/v1/conversations",
    operation_id="listConversations",
    responses=_ERRORS,
)
async def list_conversations(
    request: Request,
    service: Annotated[Any, Depends(get_conversation_service)],
) -> ConversationListResponse:
    """Lista as conversas do membro, da mais recente para a mais antiga."""
    records = await service.list_for_member(request.cookies.get(SESSION_COOKIE_NAME))
    return ConversationListResponse(
        conversations=[
            ConversationSummaryResponse(id=record.id, created_at=record.created_at)
            for record in records
        ]
    )


@router.get(
    "/v1/conversations/{conversation_id}",
    operation_id="getConversation",
    responses=_ERRORS,
)
async def get_conversation(
    conversation_id: UUID,
    request: Request,
    service: Annotated[Any, Depends(get_conversation_service)],
) -> ConversationResponse:
    """Devolve a conversa do dono, com mensagens e citações."""
    conversation, messages = await service.get(
        conversation_id,
        session_secret=request.cookies.get(SESSION_COOKIE_NAME),
        guest_secret=request.cookies.get(GUEST_COOKIE_NAME),
    )
    return ConversationResponse(
        id=conversation.id,
        created_at=conversation.created_at,
        messages=[
            MessageResponse(
                id=message.id,
                role=_role(message.role),
                content=message.content,
                client_message_id=message.client_message_id,
                citations=[
                    CitationResponse(
                        index=citation.index,
                        document_title=citation.document_title,
                        heading=citation.heading,
                        chunk_id=citation.chunk_id,
                    )
                    for citation in message.citations
                ],
                outcome=message.outcome,
                created_at=message.created_at,
            )
            for message in messages
        ],
    )


@router.post(
    "/v1/conversations/{conversation_id}/messages",
    operation_id="askQuestion",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "Eventos meta, token, replace, citation, done e error.",
        },
        **_ERRORS,
    },
)
async def ask_question(
    conversation_id: UUID,
    body: AskRequest,
    request: Request,
    service: Annotated[Any, Depends(get_conversation_service)],
) -> StreamingResponse:
    """Pergunta do dono. Responde com text/event-stream."""
    prepared = await service.prepare_ask(
        conversation_id,
        text=body.text,
        client_message_id=body.client_message_id,
        session_secret=request.cookies.get(SESSION_COOKIE_NAME),
        guest_secret=request.cookies.get(GUEST_COOKIE_NAME),
        client_ip=_ip(request),
        request_id=current_request_id(),
    )
    disconnected = asyncio.Event()

    async def chunks() -> AsyncIterator[str]:
        watch = asyncio.create_task(_watch_disconnect(request, disconnected))
        try:
            async for event in service.stream(prepared, disconnected):
                yield render_ask_event(event)
        finally:
            disconnected.set()
            watch.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watch

    return StreamingResponse(chunks(), media_type="text/event-stream", headers=_STREAM_HEADERS)


@router.post(
    "/v1/messages/{message_id}/feedback",
    operation_id="createFeedback",
    status_code=201,
    responses=_ERRORS,
)
async def create_feedback(
    message_id: UUID,
    body: FeedbackRequest,
    request: Request,
    background: BackgroundTasks,
    service: Annotated[Any, Depends(get_conversation_service)],
) -> FeedbackResponse:
    """Marca uma resposta do assistente como útil ou não útil, uma vez."""
    notice = await service.submit_feedback(
        message_id,
        body.rating,
        session_secret=request.cookies.get(SESSION_COOKIE_NAME),
        guest_secret=request.cookies.get(GUEST_COOKIE_NAME),
    )
    if notice is not None:
        background.add_task(service.deliver_feedback, notice)
    return FeedbackResponse(message_id=message_id, rating=body.rating)


@router.get(
    "/v1/diagnostics/stream",
    operation_id="diagnosticsStream",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "Três eventos tick, com um segundo de intervalo.",
        },
        429: {"model": ErrorResponse},
    },
)
async def diagnostics_stream(
    request: Request,
    service: Annotated[Any, Depends(get_conversation_service)],
) -> StreamingResponse:
    """Emite três eventos tick para o teste de fumaça do fluxo."""
    await service.prepare_diagnostics(_ip(request))

    async def chunks() -> AsyncIterator[str]:
        async for index in iter_diagnostic_indexes(DIAGNOSTIC_TICK_INTERVAL_SECONDS):
            yield format_event("tick", {"index": index})

    return StreamingResponse(chunks(), media_type="text/event-stream", headers=_STREAM_HEADERS)


_STREAM_HEADERS = {"cache-control": "no-store", "x-accel-buffering": "no"}


def render_ask_event(event: AskEvent) -> str:
    if isinstance(event, CommentEvent):
        return format_comment(event.text)
    if isinstance(event, MetaEvent):
        return format_event(
            "meta",
            {"message_id": str(event.message_id), "request_id": event.request_id},
        )
    if isinstance(event, TokenEvent):
        return format_event("token", {"text": event.text})
    if isinstance(event, ReplaceEvent):
        return format_event("replace", {"text": event.text, "reason": event.reason})
    if isinstance(event, CitationEvent):
        return format_event(
            "citation",
            {
                "index": event.index,
                "document_title": event.document_title,
                "heading": event.heading,
                "chunk_id": str(event.chunk_id),
            },
        )
    if isinstance(event, DoneEvent):
        return format_event("done", {"outcome": event.outcome})
    if isinstance(event, ErrorEvent):
        return format_event("error", {"code": event.code, "message": event.message})
    raise TypeError(type(event))


def _role(value: str) -> Literal["user", "assistant"]:
    if value == "assistant":
        return "assistant"
    return "user"


def _ip(request: Request) -> str:
    return client_ip(
        request.headers.get("x-forwarded-for"),
        None if request.client is None else request.client.host,
    )


async def _watch_disconnect(request: Request, disconnected: asyncio.Event) -> None:
    """O StreamingResponse do ASGI 2.4 não observa o fechamento. Este laço observa."""
    while not disconnected.is_set():
        message = await request.receive()
        if message["type"] == "http.disconnect":
            disconnected.set()
            return
