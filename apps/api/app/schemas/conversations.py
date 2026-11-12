"""Pedidos e respostas das conversas. Seção 12 do SDD.

Camada de schema (seção 6.2 do SDD). Usados pelo controlador `conversations`. A pergunta
responde em `text/event-stream`, e os eventos do fluxo não têm modelo aqui: o controlador os
escreve à mão (seção 7.1).
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.questions import MAX_QUESTION_CHARS


# Corpo de `POST /v1/conversations/{id}/messages` (seção 7.1). `client_message_id` é o UUID
# que o navegador gera para a pergunta, a chave de idempotência do envio. O `Field` confere o
# texto como chegou, de 1 a `MAX_QUESTION_CHARS` (1.000) caracteres, e o validador tira os
# espaços das pontas e recusa o que sobra vazio. Campo extra, texto inválido ou id que não é
# UUID respondem 422.
class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    client_message_id: UUID

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        """Devolve o texto sem os espaços das pontas, que substitui o valor recebido.

        `field_validator` roda depois do tipo e dos limites do `Field`. Um texto só de espaços
        sobra vazio e levanta `ValueError`, que o FastAPI responde como 422.
        """
        stripped = value.strip()
        if not stripped or len(stripped) > MAX_QUESTION_CHARS:
            raise ValueError("invalid question length")
        return stripped


# Corpo de `POST /v1/messages/{id}/feedback`. `Literal[-1, 1]` só aceita esses dois números.
class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: Literal[-1, 1]


# Resposta 201 de `POST /v1/conversations`.
class ConversationCreatedResponse(BaseModel):
    id: UUID
    created_at: datetime


# Item de `GET /v1/conversations`. `first_question` é a primeira pergunta gravada, ou `null`.
# O nome repete o de `app.schemas.insights`, e por isso o OpenAPI chama os dois pelo caminho
# do módulo: `app__schemas__conversations__ConversationSummaryResponse` e
# `app__schemas__insights__ConversationSummaryResponse`.
class ConversationSummaryResponse(BaseModel):
    id: UUID
    created_at: datetime
    first_question: str | None


# Resposta de `GET /v1/conversations`, da conversa mais recente para a mais antiga.
class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummaryResponse]


# Uma citação mantida de uma resposta, com os mesmos campos do evento `citation` do fluxo.
class CitationResponse(BaseModel):
    index: int
    document_title: str
    heading: str | None
    chunk_id: UUID


# Uma mensagem de `GET /v1/conversations/{id}`. Pergunta tem `outcome` nulo e citações vazias.
# Uma mensagem do atendimento humano tem `handoff_id`, e `role` pode ser `attendant`, a equipe;
# `redaction` diz por que o texto virou marcador (seção 29.10).
class MessageResponse(BaseModel):
    id: UUID
    role: Literal["user", "assistant", "attendant"]
    content: str
    client_message_id: UUID | None
    citations: list[CitationResponse]
    outcome: str | None
    created_at: datetime
    handoff_id: UUID | None = None
    redaction: str | None = None


# O resumo de um atendimento humano da conversa, sem quem atendeu (seção 29.10, D-9).
class HandoffSummaryResponse(BaseModel):
    id: UUID
    status: Literal["queued", "assigned", "closed"]
    close_reason: str | None
    requested_at: datetime
    assigned_at: datetime | None
    closed_at: datetime | None


# Resposta de `GET /v1/conversations/{id}`: a conversa do dono, com as mensagens em ordem e os
# atendimentos humanos dela. A visão consulta esta rota quando o fluxo cai antes do primeiro
# evento (seção 7.1).
class ConversationResponse(BaseModel):
    id: UUID
    created_at: datetime
    messages: list[MessageResponse]
    handoffs: list[HandoffSummaryResponse] = Field(default_factory=list)


# Resposta 201 do feedback: a mensagem e a nota gravadas.
class FeedbackResponse(BaseModel):
    message_id: UUID
    rating: Literal[-1, 1]
