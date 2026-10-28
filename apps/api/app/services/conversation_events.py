"""Eventos do fluxo de uma pergunta, sem banco. Seção 7.1 do SDD."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class MetaEvent:
    message_id: UUID
    request_id: str


@dataclass(frozen=True, slots=True)
class TokenEvent:
    text: str


@dataclass(frozen=True, slots=True)
class ReplaceEvent:
    text: str
    reason: Literal["grounding_failed"]


@dataclass(frozen=True, slots=True)
class CitationEvent:
    index: int
    document_title: str
    heading: str | None
    chunk_id: UUID


@dataclass(frozen=True, slots=True)
class DoneEvent:
    outcome: str


@dataclass(frozen=True, slots=True)
class ErrorEvent:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class CommentEvent:
    text: str


AskEvent = (
    MetaEvent | TokenEvent | ReplaceEvent | CitationEvent | DoneEvent | ErrorEvent | CommentEvent
)
