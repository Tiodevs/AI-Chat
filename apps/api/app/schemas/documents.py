"""Respostas da gestão de documentos do admin. Seção 12 do SDD.

Camada de schema (seção 6.2 do SDD). Usados pelo controlador `admin_documents`. O upload e a
substituição chegam em multipart (`file` e `title`), declarados na própria rota, e o FastAPI
gera para eles os modelos `Body_uploadDocument` e `Body_replaceDocument` do OpenAPI. Seções 7.3
e 15.5 do SDD.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.domain.documents import DocumentView, VersionView


# Uma versão na tela de documentos, sem os bytes e sem o texto extraído. Os `Literal` repetem
# as restrições de `document_versions` e de `documents` no banco, para o OpenAPI e os tipos do
# frontend listarem os valores possíveis.
class DocumentVersionResponse(BaseModel):
    id: UUID
    version: int
    filename: str
    media_type: str
    byte_size: int
    ingestion_status: Literal["processing", "ready", "failed"]
    error: str | None
    created_at: datetime


# Um documento com a versão ativa e a última versão; as duas podem ser nulas e podem ser a
# mesma. Resposta de `POST /v1/admin/documents` (201), de `replace` e `retry` (202) e de
# `archive` (200), e item de `GET /v1/admin/documents`.
class DocumentResponse(BaseModel):
    id: UUID
    title: str
    slug: str
    status: Literal["active", "archived"]
    created_at: datetime
    updated_at: datetime
    active_version: DocumentVersionResponse | None
    latest_version: DocumentVersionResponse | None


# Resposta de `GET /v1/admin/documents`: ativos primeiro, depois os arquivados, do mais
# recente ao mais antigo.
class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]


def version_response(version: VersionView | None) -> DocumentVersionResponse | None:
    """Converte a versão do domínio no modelo de resposta, ou `None` sem versão.

    `model_validate(..., from_attributes=True)` lê os atributos do dataclass, em vez de
    esperar um dicionário.
    """
    if version is None:
        return None
    return DocumentVersionResponse.model_validate(version, from_attributes=True)


def document_response(view: DocumentView) -> DocumentResponse:
    """Converte a visão do domínio no modelo de resposta do admin."""
    return DocumentResponse(
        id=view.id,
        title=view.title,
        slug=view.slug,
        status=view.status,
        created_at=view.created_at,
        updated_at=view.updated_at,
        active_version=version_response(view.active_version),
        latest_version=version_response(view.latest_version),
    )
