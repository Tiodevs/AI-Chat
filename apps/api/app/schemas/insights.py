"""Respostas da visão geral, da qualidade e do inspetor. Seção 12 do SDD.

Camada de schema (seção 6.2 do SDD). Usados pelo controlador `admin_insights`. Nenhum modelo
de conversa traz nome ou e-mail: o admin vê pseudônimos, e só `IdentityResponse`, depois de
um motivo, revela a pessoa (seção 11.8). Seção 15.5 do SDD.
"""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# Um indicador do período contra o período anterior de mesmo tamanho. Uma taxa sem
# denominador sai `null`.
class MetricResponse(BaseModel):
    current: float | None
    previous: float | None


# Um dia UTC da tendência. O serviço manda todos os dias que o período toca, com zero nos dias
# sem pergunta.
class TrendPointResponse(BaseModel):
    date: date
    questions: int
    answered: int


# Uma etapa do funil de cadastro, contada por caminho.
class FunnelRowResponse(BaseModel):
    step: Literal["started", "password_set", "completed"]
    chat: int
    form: int


# Uso do dia UTC contra `LLM_DAILY_TOKEN_BUDGET`. `ratio` é 0 com o teto desligado.
class BudgetResponse(BaseModel):
    used_tokens: int
    daily_budget: int
    ratio: float


# Resposta de `GET /v1/admin/overview?period_days=7` ou `30`. `outcomes`, `intents` e
# `feedback` são contagens com todas as chaves, inclusive as zeradas; a intenção é derivada
# do desfecho gravado (seção 15.5).
class OverviewResponse(BaseModel):
    period_days: int
    generated_at: datetime
    questions: MetricResponse
    answer_rate: MetricResponse
    abstention_rate: MetricResponse
    helpful_rate: MetricResponse
    trend: list[TrendPointResponse]
    outcomes: dict[str, int]
    intents: dict[str, int]
    feedback: dict[str, int]
    funnel: list[FunnelRowResponse]
    budget: BudgetResponse


# Uma conversa na tabela de qualidade. `pseudonym` são 8 caracteres do HMAC de `PSEUDONYM_KEY`
# sobre o id do membro ou da chave de convidado. Mesmo nome de classe que em
# `app.schemas.conversations`; no OpenAPI, este vira
# `app__schemas__insights__ConversationSummaryResponse`.
class ConversationSummaryResponse(BaseModel):
    id: UUID
    subject_kind: Literal["guest", "member"]
    pseudonym: str
    started_at: datetime
    last_activity_at: datetime
    questions: int
    last_outcome: str | None
    helpful: int
    not_helpful: int


# Resposta de `GET /v1/admin/quality`. `outcomes` e `feedback` contam todas as conversas do
# período; `conversations` lista só as que o inspetor pode abrir, até 50.
class QualityResponse(BaseModel):
    period_days: int
    outcomes: dict[str, int]
    feedback: dict[str, int]
    conversations: list[ConversationSummaryResponse]


# Citação no inspetor: índice, título e seção, sem o id do chunk.
class InspectorCitationResponse(BaseModel):
    index: int
    document_title: str
    heading: str | None


# Uma mensagem no inspetor, com o que ajuda a investigar uma resposta ruim: versão do prompt,
# modelo, `request_id`, latência, o id do rastro (`run_id`) e o link dele (`trace_url`), nulo
# sem `LANGSMITH_RUN_URL_TEMPLATE`.
class InspectorMessageResponse(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    outcome: str | None
    prompt_version: str | None
    model: str | None
    request_id: str | None
    latency_ms: int | None
    run_id: UUID | None
    trace_url: str | None
    citations: list[InspectorCitationResponse]
    rating: int | None


# Resposta de `GET /v1/admin/conversations/{id}`. Abrir a conversa grava `conversation.view`.
class InspectionResponse(BaseModel):
    id: UUID
    subject_kind: Literal["guest", "member"]
    pseudonym: str
    created_at: datetime
    messages: list[InspectorMessageResponse]


# Corpo de `POST /v1/admin/conversations/{id}/reveal`. O `max_length=2000` é um limite
# externo. A regra de 10 a 500 caracteres, depois de juntar os espaços, é do domínio e volta
# em `field_errors.reason`; acima de 2.000, o corpo falha aqui e o 422 sai sem `field_errors`.
class RevealRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(max_length=2000)


# Resposta da revelação. A mesma transação grava `identity.reveal` com o motivo.
class IdentityResponse(BaseModel):
    conversation_id: UUID
    full_name: str
    email: str
