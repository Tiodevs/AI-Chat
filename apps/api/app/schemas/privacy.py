"""Canal do titular e fila do admin. Seção 12 do SDD.

Camada de schema (seção 6.2 do SDD). O controlador `privacy` usa os modelos do canal público,
e o `admin_privacy`, os da fila. Os limites daqui são externos: barram um corpo absurdo com 422
sem `field_errors`. As regras finas (tamanho da descrição e da nota, caractere de controle,
endereço seguro) ficam no domínio e voltam em `field_errors`. Seções 11.5 e 15.5 do SDD.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# Corpo de `POST /v1/privacy/requests`. O domínio aceita descrição de até 2.000 caracteres;
# entre 2.001 e 4.000, o erro volta em `field_errors`, e acima disso o corpo falha aqui.
class PrivacyRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact_email: str = Field(max_length=320)
    request_type: str = Field(max_length=40)
    description: str = Field(max_length=4000)


# Resposta 201 do canal: o pedido nasce `open`, com `due_at` 15 dias depois de `received_at`.
class PrivacyRequestResponse(BaseModel):
    id: UUID
    request_type: str
    status: str
    received_at: datetime
    due_at: datetime


# Corpo de `PATCH /v1/admin/privacy/requests/{id}`. A docstring abaixo já está no OpenAPI.
# Status acima de 40 caracteres, nota acima de 4.000 ou campo extra falham aqui (seção 12).
class PrivacyRequestUpdate(BaseModel):
    """Status e nota de resolução. Os limites finos ficam no domínio, com `field_errors`."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(max_length=40)
    resolution_note: str | None = Field(default=None, max_length=4000)


# Um pedido na fila do admin, também a resposta do `PATCH`. `overdue` é um pedido aberto com
# `due_at` antes de `generated_at`. `linked_account` diz que o pedido veio com sessão e a
# conta ainda existe.
class PrivacyQueueItemResponse(BaseModel):
    id: UUID
    request_type: str
    status: str
    contact_email: str
    description: str
    received_at: datetime
    due_at: datetime
    closed_at: datetime | None
    resolution_note: str | None
    overdue: bool
    linked_account: bool


# Resposta de `GET /v1/admin/privacy/requests`: os abertos, com os atrasados no topo, e os 50
# fechados mais recentes, todos lidos no mesmo instante, `generated_at`.
class PrivacyQueueResponse(BaseModel):
    generated_at: datetime
    requests: list[PrivacyQueueItemResponse]
