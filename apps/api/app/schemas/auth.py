"""Login, perfil e a rota de prova do admin. Seção 12 do SDD.

Camada de schema (seção 6.2 do SDD). Usados pelos controladores `auth`, `account`,
`registration` e `admin_probe`.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# Corpo de `POST /v1/auth/login`. `model_config = ConfigDict(extra="forbid")` faz o Pydantic
# recusar campo desconhecido, e o FastAPI responde 422 sem chamar o controlador. Os
# `Field(max_length=...)` são limites externos, para barrar um corpo absurdo. A regra fina é do
# domínio: senha fora de 1 a 72 caracteres nem chega ao argon2 e vira credencial inválida.
class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(max_length=320)
    password: str = Field(max_length=1024)


# O perfil de `GET /v1/me`. Volta também em `PATCH /v1/me`, `POST /v1/auth/login`,
# `POST /v1/registration/sessions/{id}/acceptance` e `POST /v1/registration/form`. Não tem
# `password_hash` (seção 12). `needs_legal_acceptance` é verdadeiro quando não há aceite
# vigente da `LEGAL_DOCUMENT_VERSION`.
class ProfileResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    phone: str | None
    visitor_type: str | None
    visit_reason: str | None
    role: str
    needs_legal_acceptance: bool


# Resposta de `GET /v1/admin/probe`, rota fora do OpenAPI (`include_in_schema=False`) que só
# prova a autorização de admin. A Etapa 13.5 remove a rota.
class AdminProbeResponse(BaseModel):
    status: str
