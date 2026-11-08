"""Pedidos e respostas do cadastro. Seção 12 do SDD.

Camada de schema (seção 6.2 do SDD). Usados pelo controlador `registration`, pelo chat e pelo
formulário. Os limites daqui são externos e respondem 422 sem `field_errors`. As regras de
campo da seção 8.5 ficam no domínio, as mesmas no chat e no formulário, e voltam em
`field_errors`. Seção 7.2 do SDD.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.registration import MAX_MESSAGE_CHARS


# Corpo de `POST /v1/registration/sessions/{id}/messages`, um turno do chat. O texto vai de 1 a
# `MAX_MESSAGE_CHARS` (1.000) caracteres, conferido como chegou e de novo sem os espaços das
# pontas.
class RegistrationMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        """Devolve o texto sem os espaços das pontas, que substitui o valor recebido.

        Roda depois do tipo e dos limites do `Field`. Uma mensagem só de espaços levanta
        `ValueError`, e o FastAPI responde 422.
        """
        stripped = value.strip()
        if not stripped or len(stripped) > MAX_MESSAGE_CHARS:
            raise ValueError("invalid registration message")
        return stripped


# Corpo de `POST /v1/registration/sessions/{id}/password`. A docstring abaixo já está no
# OpenAPI. A regra de 12 a 72 caracteres é do domínio (seção 8.5), e o serviço grava só o hash.
class PasswordRequest(BaseModel):
    """A senha só entra por este pedido ou pelo formulário. Não vai para o modelo."""

    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1, max_length=200)


# Corpo de `POST /v1/registration/sessions/{id}/review`: `true` confirma o resumo, `false`
# volta para corrigir um campo.
class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accept: bool


# Corpo de `POST /v1/registration/sessions/{id}/acceptance`, os aceites da seção 7.2. O
# domínio exige `accept_terms`, `age_18_plus` e `document_version` igual à versão vigente; os
# dois consentimentos opcionais valem `false` quando ausentes.
class AcceptanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accept_terms: bool
    document_version: str = Field(min_length=1, max_length=64)
    age_18_plus: bool
    profile_personalization: bool = False
    quality_improvement: bool = False


# Corpo de `POST /v1/registration/form`: campos, senha e aceites num pedido só, pela mesma
# conclusão do chat. `session_id` liga o formulário a uma sessão de chat já aberta. Sem ele,
# o serviço grava uma sessão nova, já concluída.
class FormRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID | None = None
    full_name: str = Field(max_length=200)
    email: str = Field(max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    visitor_type: str | None = Field(default=None, max_length=40)
    visit_reason: str | None = Field(default=None, max_length=40)
    password: str = Field(min_length=1, max_length=200)
    accept_terms: bool
    document_version: str = Field(min_length=1, max_length=64)
    age_18_plus: bool
    profile_personalization: bool = False
    quality_improvement: bool = False


# Corpo de `PATCH /v1/registration/sessions/{id}/fields`, a edição no cartão de resumo. O
# controlador lê `model_fields_set`, os campos presentes no JSON: um campo ausente não muda,
# e um `null` enviado limpa. Sem `max_length` aqui; as regras de tamanho são as do domínio.
class FieldsPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    visitor_type: str | None = None
    visit_reason: str | None = None


# Os cinco campos que o cadastro entendeu até agora, nulos quando ainda faltam.
class RegistrationFieldsResponse(BaseModel):
    full_name: str | None
    email: str | None
    phone: str | None
    visitor_type: str | None
    visit_reason: str | None


# Um item da transcrição: `{role, text, created_at}`. A docstring abaixo já está no OpenAPI.
# Num modelo de resposta, `extra="forbid"` aparece no contrato como
# `additionalProperties: false`.
class TranscriptMessageResponse(BaseModel):
    """Serializador da transcrição. Não tem campo de senha."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    text: str
    created_at: datetime


# A sessão de cadastro: resposta 201 de `POST /v1/registration/sessions` e 200 dos outros
# pedidos da sessão. `next_step` diz à tela o que mostrar, inclusive o campo de senha quando
# vale `password` (seção 7.2), e `prompt` é a frase do assistente para esse passo.
class RegistrationSessionResponse(BaseModel):
    id: UUID
    status: str
    path: Literal["chat", "form"]
    fields: RegistrationFieldsResponse
    field_errors: dict[str, str]
    next_step: str
    prompt: str
    messages: list[TranscriptMessageResponse]
    expires_at: datetime
