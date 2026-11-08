"""Pedidos e respostas da conta do membro. Seção 12 do SDD.

Camada de schema (seção 6.2 do SDD). Usados pelo controlador `account`: correção do perfil,
consentimentos e exportação do titular. A exclusão da conta não tem corpo. Seções 11.5 e 15.5
do SDD.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# Corpo de `PATCH /v1/me`. O controlador usa `model_dump(exclude_unset=True)`: só entram os
# campos presentes no JSON, então um campo ausente não muda e um `null` enviado limpa. O
# e-mail não está aqui e, com `extra="forbid"`, mandá-lo responde 422. Os `max_length` são
# limites externos; as regras da seção 8.5 ficam no domínio e voltam em `field_errors`. A
# docstring abaixo já está no OpenAPI.
class ProfilePatchRequest(BaseModel):
    """Só os campos enviados mudam. `null` limpa um campo opcional."""

    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    visitor_type: str | None = Field(default=None, max_length=40)
    visit_reason: str | None = Field(default=None, max_length=40)


# Corpo de `PUT /v1/me/consents/{purpose}`. A finalidade vem do caminho, e o domínio decide
# o que cada uma aceita: os Termos só aceitam `true`, e a maioridade não muda (seção 12).
class ConsentChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    granted: bool


# Uma linha de `consent_records`, sem `id` nem `user_id`. Forma o `history` de
# `GET /v1/me/consents`, do mais novo ao mais antigo, e os `consents` da exportação.
class ConsentItemResponse(BaseModel):
    purpose: str
    document_version: str
    granted_at: datetime
    revoked_at: datetime | None
    source: str


# O estado atual de uma finalidade: `granted` e a versão e a data da concessão vigente mais
# recente, nulas sem concessão vigente.
class ConsentStateResponse(BaseModel):
    purpose: str
    granted: bool
    document_version: str | None
    granted_at: datetime | None


# Resposta de `GET /v1/me/consents` e de `PUT /v1/me/consents/{purpose}`: um item por
# finalidade em `current` e todas as linhas em `history`.
class ConsentsResponse(BaseModel):
    current: list[ConsentStateResponse]
    history: list[ConsentItemResponse]


# Os modelos `Export*` formam o JSON de `GET /v1/me/export` (seção 11.5). O controlador os
# serializa num `JSONResponse` com `Content-Disposition: attachment`; o `response_model` da
# rota só descreve o arquivo no OpenAPI. Ficam de fora o hash da senha, os ids do usuário, de
# chunk e de rastro.
class ExportProfile(BaseModel):
    email: str
    full_name: str
    phone: str | None
    visitor_type: str | None
    visit_reason: str | None
    role: str
    created_at: datetime


# Citação exportada: índice, título e seção, sem `chunk_id`.
class ExportCitation(BaseModel):
    index: int
    document_title: str
    heading: str | None


# Uma mensagem exportada, com a nota que o titular deu, se houver (`1` ou `-1`).
class ExportMessage(BaseModel):
    role: str
    content: str
    citations: list[ExportCitation]
    outcome: str | None
    feedback: int | None
    created_at: datetime


# Uma conversa do titular. O serviço as exporta da mais antiga para a mais nova, com as
# mensagens em ordem cronológica.
class ExportConversation(BaseModel):
    id: UUID
    created_at: datetime
    messages: list[ExportMessage]


# O arquivo inteiro: data da exportação, perfil, consentimentos e conversas.
class ExportResponse(BaseModel):
    exported_at: datetime
    profile: ExportProfile
    consents: list[ConsentItemResponse]
    conversations: list[ExportConversation]
