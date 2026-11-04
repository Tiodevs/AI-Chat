"""Respostas da gestão de documentos do admin. Seção 12 do SDD."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.domain.documents import DocumentView, VersionView


class DocumentVersionResponse(BaseModel):
    id: UUID
    version: int
    filename: str
    media_type: str
    byte_size: int
    ingestion_status: Literal["processing", "ready", "failed"]
    error: str | None
    created_at: datetime


class DocumentResponse(BaseModel):
    id: UUID
    title: str
    slug: str
    status: Literal["active", "archived"]
    created_at: datetime
    updated_at: datetime
    active_version: DocumentVersionResponse | None
    latest_version: DocumentVersionResponse | None


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]


def version_response(version: VersionView | None) -> DocumentVersionResponse | None:
    if version is None:
        return None
    return DocumentVersionResponse.model_validate(version, from_attributes=True)


def document_response(view: DocumentView) -> DocumentResponse:
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
