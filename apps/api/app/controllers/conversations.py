"""Conversas, fluxo SSE e o diagnóstico do rewrite. Seções 7.1 e 12.

Camada de controle. Todas as rotas recebem o `ConversationService` de
`app.core.container.get_conversation_service`, com o `QaWorkflow` do `AiRuntime`. O dono de
uma conversa é a sessão (`atrium_session`) ou a chave de convidado (`atrium_guest`): o
controlador só lê os dois cookies e deixa o serviço decidir.

A pergunta tem duas fases. `prepare_ask` valida e confere dono, idempotência e limite de taxa
antes de qualquer byte do fluxo, então um erro ali ainda sai como JSON com o envelope da
seção 12. Depois, `service.stream` produz os eventos, e `render_ask_event` os converte no
texto SSE. Os eventos vêm de `app.services.conversation_events`, que não importa SQLAlchemy.

A docstring de cada rota é a `description` da operação no OpenAPI (seção 6.6); a explicação
a mais fica em comentários, para não mudar o contrato.
"""

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

# Status de erro documentados no OpenAPI, todos com o envelope `ErrorResponse`.
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
    # Com `atrium_session`, a conversa é do membro, e uma sessão inválida responde 401. Sem
    # sessão, o serviço reaproveita a chave de convidado do cookie ou cria uma nova e devolve
    # o cookie `atrium_guest`, que esta rota grava no `response` injetado. Responde 201.
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
    # Só com `atrium_session`; um convidado recebe 401. `first_question` é a primeira pergunta
    # gravada, ou `null` (seção 12).
    records = await service.list_for_member(request.cookies.get(SESSION_COOKIE_NAME))
    return ConversationListResponse(
        conversations=[
            ConversationSummaryResponse(
                id=record.id,
                created_at=record.created_at,
                first_question=question,
            )
            for record, question in records
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
    # Conversa inexistente e cookie que não é do dono respondem o mesmo 404 (Etapa 15.1). É a
    # rota que a visão consulta quando o fluxo não entrega o primeiro evento (seção 7.1).
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
    # Passos:
    # 1. `prepare_ask` valida o texto, confere o dono, o `client_message_id` repetido (409 com
    #    `message_id`) e o limite de taxa (429), lê o histórico e consulta o orçamento. Um erro
    #    aqui sai como JSON, antes do fluxo.
    # 2. No primeiro pedaço do fluxo, uma tarefa passa a observar a desconexão do cliente.
    # 3. O `StreamingResponse` consome `service.stream`: `meta` primeiro, depois os tokens, a
    #    manutenção a cada 15 s sem token e o fim (seção 7.1).
    # 4. Ao fim do fluxo, normal ou cortado, a tarefa de observação é encerrada.
    #
    # 1.
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

    # O gerador só começa a rodar quando o Starlette pede o primeiro pedaço, depois de esta
    # função devolver a resposta.
    async def chunks() -> AsyncIterator[str]:
        # 2.
        watch = asyncio.create_task(_watch_disconnect(request, disconnected))
        try:
            # 3.
            async for event in service.stream(prepared, disconnected):
                yield render_ask_event(event)
        finally:
            # 4. Marca a desconexão também no fim normal, para quem ainda espera por ela.
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
    # Responde 201. Mensagem inexistente ou de conversa de outro dono responde 404; mensagem do
    # visitante, 422; segunda nota na mesma mensagem, 409. Quando a resposta tem rastro, o
    # envio ao LangSmith (`user_helpful`) vai para uma tarefa de fundo, que o Starlette roda
    # depois de enviar a resposta; uma falha nela só gera log (seção 18.4).
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
    # Conta o pedido no balde de 60 por hora por IP antes do fluxo (429 acima). Não chama o
    # modelo: com o provedor indisponível, a rota continua respondendo (seção 17).
    await service.prepare_diagnostics(_ip(request))

    async def chunks() -> AsyncIterator[str]:
        async for index in iter_diagnostic_indexes(DIAGNOSTIC_TICK_INTERVAL_SECONDS):
            yield format_event("tick", {"index": index})

    return StreamingResponse(chunks(), media_type="text/event-stream", headers=_STREAM_HEADERS)


# Lido só quando uma rota de fluxo roda, com o módulo já carregado; por isso pode vir depois
# delas. O `no-store` também vem do `ApiGuardMiddleware`. `x-accel-buffering: no` pede a um
# proxy no caminho, como o nginx, que não segure os eventos.
_STREAM_HEADERS = {"cache-control": "no-store", "x-accel-buffering": "no"}


def render_ask_event(event: AskEvent) -> str:
    """Converte um evento do serviço no texto SSE da seção 7.1.

    `CommentEvent` vira o comentário `: keepalive`; os ids saem como texto. Um tipo
    desconhecido levanta `TypeError`, em vez de sumir do fluxo sem aviso.
    """
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
    """Estreita o papel gravado para o `Literal` do schema: o que não é `assistant` é `user`."""
    if value == "assistant":
        return "assistant"
    return "user"


def _ip(request: Request) -> str:
    """IP do cliente para os limites de taxa (`app.core.client_ip`)."""
    return client_ip(
        request.headers.get("x-forwarded-for"),
        None if request.client is None else request.client.host,
    )


async def _watch_disconnect(request: Request, disconnected: asyncio.Event) -> None:
    """O StreamingResponse do ASGI 2.4 não observa o fechamento. Este laço observa.

    Com o ASGI 2.4, o Starlette só nota que o cliente saiu quando um `send` falha, e um fluxo
    em silêncio, esperando o modelo, não envia nada. Este laço lê o canal `receive` até
    chegar `http.disconnect` e então marca `disconnected`, que o serviço usa para cancelar a
    resposta (seção 6.4). O corpo do pedido já foi lido antes, pelo FastAPI.
    """
    while not disconnected.is_set():
        message = await request.receive()
        if message["type"] == "http.disconnect":
            disconnected.set()
            return
