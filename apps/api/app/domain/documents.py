"""Regras do upload de documentos pelo admin. Seções 7.3, 10.4 e 12 do SDD."""

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from app.domain.auth import RateDecision, fixed_window_start, retry_after_seconds

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
TITLE_MAX_CHARS = 200
SLUG_MAX_CHARS = 80
UPLOAD_LIMIT = 30
UPLOAD_WINDOW = timedelta(hours=1)
UPLOAD_PURPOSE = "admin_upload"
PROCESSING_GRACE = timedelta(minutes=15)

_MEDIA_BY_EXTENSION = {
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
    ".pdf": "application/pdf",
}


class DocumentAction(StrEnum):
    UPLOAD = "document.upload"
    REPLACE = "document.replace"
    RETRY = "document.retry"
    ARCHIVE = "document.archive"


class UploadIssue(StrEnum):
    EMPTY = "empty"
    TOO_LARGE = "too_large"
    UNSUPPORTED_TYPE = "unsupported_type"
    NOT_UTF8 = "not_utf8"
    NOT_PDF = "not_pdf"
    TITLE_TOO_LONG = "title_too_long"


@dataclass(frozen=True, slots=True)
class AcceptedFile:
    filename: str
    media_type: str


def extension_of(filename: str) -> str:
    name = filename.strip().lower()
    dot = name.rfind(".")
    return "" if dot < 0 else name[dot:]


def stem_of(filename: str) -> str:
    name = filename.strip().replace("\\", "/").rsplit("/", 1)[-1]
    dot = name.rfind(".")
    return name if dot <= 0 else name[:dot]


def check_file(filename: str, data: bytes) -> AcceptedFile | UploadIssue:
    """Tipo pela extensão, conferido no conteúdo. O tipo declarado pelo navegador não vale."""
    media_type = _MEDIA_BY_EXTENSION.get(extension_of(filename))
    if media_type is None:
        return UploadIssue.UNSUPPORTED_TYPE
    if not data:
        return UploadIssue.EMPTY
    if len(data) > MAX_UPLOAD_BYTES:
        return UploadIssue.TOO_LARGE
    if media_type == "application/pdf":
        if not data.startswith(b"%PDF-"):
            return UploadIssue.NOT_PDF
    else:
        try:
            decoded = data.decode("utf-8")
        except UnicodeDecodeError:
            return UploadIssue.NOT_UTF8
        if "\x00" in decoded:
            return UploadIssue.NOT_UTF8
    clean_name = filename.strip().replace("\\", "/").rsplit("/", 1)[-1][:255]
    return AcceptedFile(filename=clean_name, media_type=media_type)


def clean_title(title: str | None, filename: str) -> str | UploadIssue:
    """Título enviado ou, sem ele, o nome do arquivo sem a extensão."""
    value = " ".join((title or "").split())
    if not value:
        value = " ".join(stem_of(filename).replace("_", " ").split()) or filename
    if len(value) > TITLE_MAX_CHARS:
        return UploadIssue.TITLE_TOO_LONG
    return value


def slugify(value: str) -> str:
    """Slug em ASCII, minúsculo, com hífens. Nunca vazio."""
    ascii_text = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")[:SLUG_MAX_CHARS].strip("-")
    return slug or "documento"


def numbered_slug(base: str, taken: set[str]) -> str:
    """Primeiro slug livre: base, base-2, base-3..."""
    if base not in taken:
        return base
    number = 2
    while f"{base}-{number}" in taken:
        number += 1
    return f"{base}-{number}"


def processing_is_recent(created_at: datetime, now: datetime) -> bool:
    """Uma versão em processing há menos de 15 minutos ainda pode terminar."""
    return now - created_at < PROCESSING_GRACE


def upload_window_start(now: datetime) -> datetime:
    return fixed_window_start(now, UPLOAD_WINDOW)


def upload_rate_decision(*, count: int, now: datetime, window_start: datetime) -> RateDecision:
    if count <= UPLOAD_LIMIT:
        return RateDecision(limited=False, retry_after_seconds=0)
    return RateDecision(
        limited=True,
        retry_after_seconds=retry_after_seconds(now, window_start, UPLOAD_WINDOW),
    )


@dataclass(frozen=True, slots=True)
class VersionView:
    id: UUID
    version: int
    filename: str
    media_type: str
    byte_size: int
    ingestion_status: str
    error: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DocumentView:
    id: UUID
    title: str
    slug: str
    status: str
    created_at: datetime
    updated_at: datetime
    active_version: VersionView | None
    latest_version: VersionView | None


@dataclass(frozen=True, slots=True)
class StoredVersion:
    """A última versão com os bytes originais, para tentar de novo."""

    id: UUID
    filename: str
    media_type: str
    sha256: str
    ingestion_status: str
    created_at: datetime
    original_bytes: bytes
