"""Pedidos e respostas do atendimento humano, do visitante e da equipe. Seção 29.10 do SDD.

Camada de schema (seção 6.2). Usados por `controllers/handoff.py`, `controllers/attendance.py`
e `controllers/admin_handoffs.py`. Os fluxos SSE não têm modelo aqui: os serviços escrevem os
eventos (seção 29.6). Nenhuma resposta da fila ou da lista de encerrados tem conteúdo, nome,
e-mail ou tipo de visitante (seção 29.9.4). Campo extra no corpo responde 422.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.handoff import MAX_STAFF_CHARS, MAX_VISITOR_CHARS

HandoffStatusValue = Literal["queued", "assigned", "closed"]
AvailabilityValue = Literal["open", "busy", "closed", "disabled"]
PresenceValue = Literal["available", "away"]


# `GET /v1/handoff/availability`: um status só, sem dizer quantas pessoas estão presentes.
class AvailabilityResponse(BaseModel):
    status: AvailabilityValue


# Corpo de `POST /v1/conversations/{id}/handoff`: a resposta que motivou o pedido.
class HandoffRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trigger_message_id: UUID


# O atendimento como o visitante o vê. Sem quem atende (D-9).
class HandoffResponse(BaseModel):
    id: UUID
    status: HandoffStatusValue
    queue_position: int | None
    close_reason: str | None
    requested_at: datetime
    assigned_at: datetime | None
    closed_at: datetime | None
    seq: int


# Corpo da mensagem do visitante. A remoção de identificadores roda depois, no serviço.
class VisitorMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=MAX_VISITOR_CHARS)
    client_message_id: UUID


# Uma mensagem do atendimento, já como foi gravada, com os marcadores (seção 29.6).
class HandoffMessageResponse(BaseModel):
    id: UUID
    seq: int
    role: Literal["user", "attendant"]
    content: str
    redaction: str | None
    created_at: datetime
    # Só na mensagem da equipe num atendimento do WhatsApp, para o console (seção 30.5):
    # `pending`, `sent`, `delivered`, `read` ou `failed`, e o motivo em texto da falha.
    delivery: Literal["pending", "sent", "delivered", "read", "failed"] | None = None
    delivery_error: str | None = None


# `GET /v1/attendance/me` e as respostas do aceite e da presença.
class AttendanceMeResponse(BaseModel):
    presence: PresenceValue
    acknowledged: bool
    terms_version: str


# Corpo de `POST /v1/attendance/acknowledgement`: a versão vigente do compromisso.
class AcknowledgementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(min_length=1, max_length=64)


# Corpo de `PUT /v1/attendance/presence`.
class PresenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PresenceValue


# Um atendimento na fila ou na aba da equipe, sem conteúdo (seção 29.9.4).
class StaffHandoffResponse(BaseModel):
    handoff_id: UUID
    label: str
    status: HandoffStatusValue
    trigger: str
    requested_at: datetime
    queued_at: datetime
    assigned_at: datetime | None
    closed_at: datetime | None
    close_reason: str | None
    returned: bool
    visitor_present: bool
    seq: int
    # `whatsapp` mostra o selo do canal no console, sem identidade (seção 30.11).
    channel: Literal["web", "whatsapp"] = "web"


# `GET /v1/attendance/queue`: a fila, os atendimentos da pessoa e a equipe presente.
class QueueResponse(BaseModel):
    queued: list[StaffHandoffResponse]
    mine: list[StaffHandoffResponse]
    available_attendants: int


# Uma citação de uma resposta do Atrium, para quem assumiu.
class StaffCitationResponse(BaseModel):
    index: int
    document_title: str
    heading: str | None


# Uma mensagem da conversa com a IA: pergunta, resposta, fontes e o selo do desfecho.
class ConversationLineResponse(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    content: str
    citations: list[StaffCitationResponse]
    outcome: str | None
    created_at: datetime


# O atendimento e a conversa como na seção 29.9.4.
class HandoffDetailResponse(BaseModel):
    handoff: StaffHandoffResponse
    conversation: list[ConversationLineResponse]
    messages: list[HandoffMessageResponse]


# Corpo da resposta da equipe: o texto, ou o modelo de orientação médica da seção 10.1.
class StaffMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str | None = Field(default=None, min_length=1, max_length=MAX_STAFF_CHARS)
    template: Literal["medical_emergency"] | None = None
    client_message_id: UUID


# Corpo do encerramento pela equipe: um motivo da lista fechada (seção 29.5).
class CloseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=40)


# Corpo da remoção de conteúdo: a categoria (seção 29.9.6).
class RedactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str = Field(min_length=1, max_length=40)


# Uma linha da lista de encerrados do admin, sem conteúdo.
class ClosedHandoffResponse(BaseModel):
    id: UUID
    label: str
    trigger: str
    requested_at: datetime
    assigned_at: datetime | None
    closed_at: datetime | None
    close_reason: str | None
    message_count: int
    content_purged: bool


# `GET /v1/admin/handoffs`.
class ClosedHandoffListResponse(BaseModel):
    handoffs: list[ClosedHandoffResponse]


# Corpo de `POST /v1/admin/handoffs/{id}/view`: o motivo, de 10 a 500 caracteres no serviço.
class ViewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(max_length=2000)
