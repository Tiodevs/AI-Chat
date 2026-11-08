"""Eventos do fluxo de uma pergunta, sem banco e sem HTTP. Seção 7.1 do SDD.

Camada de serviço. `ConversationService.stream` (em `conversations.py`) produz estes
objetos, e `controllers/conversations.py:render_ask_event` os converte no texto
`event: ...` e `data: ...` do `text/event-stream`. Os tipos são dataclasses neutras porque
`app.services` não pode importar FastAPI (seção 6.2): quem formata o SSE é o controlador.

A ordem dos eventos e a carga de cada um estão na tabela da seção 7.1.
"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class MetaEvent:
    """Primeiro evento de todo fluxo.

    `message_id` é o id que a resposta do assistente terá no banco, o mesmo usado como id do
    run raiz no LangSmith (seção 18.4). `request_id` liga o fluxo aos logs e rastros.
    """

    message_id: UUID
    request_id: str


@dataclass(frozen=True, slots=True)
class TokenEvent:
    """Um pedaço do rascunho em fluxo, ou o texto inteiro de uma resposta fixa num evento só."""

    text: str


@dataclass(frozen=True, slots=True)
class ReplaceEvent:
    """A fundamentação falhou depois que tokens já tinham saído.

    A visão troca o balão inteiro do assistente por `text`, a resposta fixa de abstenção.
    """

    text: str
    reason: Literal["grounding_failed"]


@dataclass(frozen=True, slots=True)
class CitationEvent:
    """Uma citação mantida pela fundamentação, com o chunk que a sustenta."""

    index: int
    document_title: str
    heading: str | None
    chunk_id: UUID


@dataclass(frozen=True, slots=True)
class DoneEvent:
    """Fim normal do fluxo. `outcome` é um valor de `domain/outcomes.py:Outcome`."""

    outcome: str


@dataclass(frozen=True, slots=True)
class ErrorEvent:
    """Entra no lugar de `done` quando o fluxo quebra depois do `meta`.

    `code` é `conflict` para um reenvio que perdeu a corrida e `error` para uma falha.
    """

    code: str
    message: str


@dataclass(frozen=True, slots=True)
class CommentEvent:
    """Comentário SSE (`: keepalive`), enviado a cada 15 s sem token.

    Não é um evento para a visão: só mantém a conexão ativa nos proxies (seção 7.1).
    """

    text: str


# Tudo o que `ConversationService.stream` pode produzir.
AskEvent = (
    MetaEvent | TokenEvent | ReplaceEvent | CitationEvent | DoneEvent | ErrorEvent | CommentEvent
)
