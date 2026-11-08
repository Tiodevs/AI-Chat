"""Regras do upload de documentos pelo admin. Seções 7.3, 10.4 e 12 do SDD.

Camada de domínio. `DocumentAdminService` (`app/services/documents.py`) aplica estas regras
antes de gravar uma versão: tipo do arquivo, título, slug, prazo de processamento e limite de
uploads. `app/controllers/admin_documents.py` lê no máximo `MAX_UPLOAD_BYTES + 1` bytes,
`DocumentRepository` monta as visões e `app/prompts/documents.py` tem a mensagem de cada
`UploadIssue`.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from app.domain.auth import RateDecision, fixed_window_start, retry_after_seconds

# 10 MB (seção 2.1). O controlador lê um byte a mais, para `check_file` reconhecer o excesso
# sem ler o arquivo inteiro.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
# Limite do título (seção 12) e do slug, em caracteres.
TITLE_MAX_CHARS = 200
SLUG_MAX_CHARS = 80
# 30 uploads por hora por admin (seção 10.4). Upload, substituição e nova tentativa contam.
UPLOAD_LIMIT = 30
UPLOAD_WINDOW = timedelta(hours=1)
UPLOAD_PURPOSE = "admin_upload"
# Uma versão em `processing` há menos de 15 minutos ainda pode terminar (seção 7.3).
# `STALE_PROCESSING_AFTER`, em `app/services/ingestion.py`, repete os 15 minutos para marcar
# como `failed`, na inicialização, a versão que passou do prazo.
PROCESSING_GRACE = timedelta(minutes=15)

# O tipo vem só da extensão (seção 12). O tipo declarado pelo navegador não conta.
_MEDIA_BY_EXTENSION = {
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
    ".pdf": "application/pdf",
}


class DocumentAction(StrEnum):
    """Ações da gestão de documentos gravadas em `audit_events` (seção 8.1)."""

    UPLOAD = "document.upload"
    REPLACE = "document.replace"
    RETRY = "document.retry"
    ARCHIVE = "document.archive"


class UploadIssue(StrEnum):
    """Motivo da recusa de um arquivo ou de um título.

    `app/prompts/documents.py` tem a mensagem de cada um. O serviço responde 422 com
    `field_errors` em `file` ou em `title` (seção 12).
    """

    EMPTY = "empty"
    TOO_LARGE = "too_large"
    UNSUPPORTED_TYPE = "unsupported_type"
    NOT_UTF8 = "not_utf8"
    NOT_PDF = "not_pdf"
    TITLE_TOO_LONG = "title_too_long"


@dataclass(frozen=True, slots=True)
class AcceptedFile:
    """Arquivo aceito por `check_file`: o nome sem a pasta e o tipo deduzido da extensão."""

    filename: str
    media_type: str


def extension_of(filename: str) -> str:
    """Extensão em minúsculas com o ponto, como `.md`, ou texto vazio sem ponto."""
    name = filename.strip().lower()
    dot = name.rfind(".")
    return "" if dot < 0 else name[dot:]


def stem_of(filename: str) -> str:
    """Nome do arquivo sem a pasta e sem a extensão.

    Aceita as duas barras como separador de pasta, para um nome com caminho de qualquer
    sistema. Um nome que começa com ponto, como `.env`, fica inteiro.
    """
    name = filename.strip().replace("\\", "/").rsplit("/", 1)[-1]
    dot = name.rfind(".")
    return name if dot <= 0 else name[:dot]


def check_file(filename: str, data: bytes) -> AcceptedFile | UploadIssue:
    """Tipo pela extensão, conferido no conteúdo. O tipo declarado pelo navegador não vale.

    1. O tipo vem da extensão: `.md`, `.markdown`, `.txt` ou `.pdf`.
    2. Arquivo vazio ou acima de 10 MB é recusado.
    3. O conteúdo confere o tipo: PDF começa com `%PDF-`; texto é UTF-8 sem caractere nulo,
       que o PostgreSQL não grava em texto.
    4. O nome guardado perde a pasta e fica com até 255 caracteres.

    Devolve o `AcceptedFile`, ou o `UploadIssue` do primeiro problema encontrado.
    """
    # 1.
    media_type = _MEDIA_BY_EXTENSION.get(extension_of(filename))
    if media_type is None:
        return UploadIssue.UNSUPPORTED_TYPE
    # 2.
    if not data:
        return UploadIssue.EMPTY
    if len(data) > MAX_UPLOAD_BYTES:
        return UploadIssue.TOO_LARGE
    # 3.
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
    # 4.
    clean_name = filename.strip().replace("\\", "/").rsplit("/", 1)[-1][:255]
    return AcceptedFile(filename=clean_name, media_type=media_type)


def clean_title(title: str | None, filename: str) -> str | UploadIssue:
    """Título enviado ou, sem ele, o nome do arquivo sem a extensão.

    Os espaços repetidos viram um só. No nome do arquivo, `_` vira espaço. Acima de 200
    caracteres, devolve `UploadIssue.TITLE_TOO_LONG` (seção 12).
    """
    value = " ".join((title or "").split())
    if not value:
        value = " ".join(stem_of(filename).replace("_", " ").split()) or filename
    if len(value) > TITLE_MAX_CHARS:
        return UploadIssue.TITLE_TOO_LONG
    return value


def slugify(value: str) -> str:
    """Slug em ASCII, minúsculo, com hífens. Nunca vazio.

    A normalização `NFKD` separa o acento da letra, e o `encode` para ASCII com `ignore`
    descarta o acento: `Horário` vira `horario`. Tudo que não é letra ou dígito vira um hífen,
    e o slug fica com até 80 caracteres. Sem nenhuma letra ou dígito, vale `documento`.
    """
    ascii_text = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")[:SLUG_MAX_CHARS].strip("-")
    return slug or "documento"


def numbered_slug(base: str, taken: set[str]) -> str:
    """Primeiro slug livre: base, base-2, base-3...

    `taken` vem de `DocumentRepository.taken_slugs`, que lê os slugs iguais a `base` ou com
    `base-` no começo.
    """
    if base not in taken:
        return base
    number = 2
    while f"{base}-{number}" in taken:
        number += 1
    return f"{base}-{number}"


def processing_is_recent(created_at: datetime, now: datetime) -> bool:
    """Uma versão em processing há menos de 15 minutos ainda pode terminar.

    Enquanto isso, substituir ou tentar de novo responde 409, para uma versão mais velha nunca
    terminar depois da nova e tomar o lugar dela (seção 7.3).
    """
    return now - created_at < PROCESSING_GRACE


def upload_window_start(now: datetime) -> datetime:
    """Começo da janela de uma hora do balde de uploads."""
    return fixed_window_start(now, UPLOAD_WINDOW)


def upload_rate_decision(*, count: int, now: datetime, window_start: datetime) -> RateDecision:
    """Decide o 429 do 31º upload do admin na hora. A contagem já inclui o pedido atual."""
    if count <= UPLOAD_LIMIT:
        return RateDecision(limited=False, retry_after_seconds=0)
    return RateDecision(
        limited=True,
        retry_after_seconds=retry_after_seconds(now, window_start, UPLOAD_WINDOW),
    )


@dataclass(frozen=True, slots=True)
class VersionView:
    """Uma versão como a lista do admin mostra (seção 12), sem os bytes nem o texto.

    `ingestion_status` é `processing`, `ready` ou `failed`. `error` traz a mensagem de
    `app/prompts/corpus.py` quando a versão falhou.
    """

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
    """Documento com a versão ativa e a mais recente, para a lista do admin (seção 12).

    `status` é `active` ou `archived`. As duas versões podem ser a mesma. `active_version` é
    `None` até a primeira versão chegar a `ready`.
    """

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
    """A última versão com os bytes originais, para tentar de novo.

    `DocumentRepository.latest_stored` a carrega, e `retry` só segue se `ingestion_status` é
    `failed`. Os bytes ficam no PostgreSQL (seção 2.1).
    """

    id: UUID
    filename: str
    media_type: str
    sha256: str
    ingestion_status: str
    created_at: datetime
    original_bytes: bytes
