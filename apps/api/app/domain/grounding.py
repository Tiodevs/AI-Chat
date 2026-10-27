"""Citação válida e telefone presente no contexto. Seção 7.1 do SDD."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

# O mesmo formato mascarado nos logs, mais o grupo 3-3-4 com espaço ou ponto.
_PHONE_RE = re.compile(
    r"(?<!\w)(?:\(\d{3}\)\s*\d{3}-\d{4}|\+\d[\d\s().-]{7,}\d|\d{3}[-.\s]\d{3}[-.\s]\d{4})(?!\w)"
)
_CITATION_RE = re.compile(r"\[(\d+)\]")


@dataclass(frozen=True, slots=True)
class ContextBlock:
    index: int
    chunk_id: UUID
    document_title: str
    heading: str | None
    content: str


@dataclass(frozen=True, slots=True)
class Citation:
    index: int
    document_title: str
    heading: str | None
    chunk_id: UUID


@dataclass(frozen=True, slots=True)
class GroundingDecision:
    grounded: bool
    citations: tuple[Citation, ...]


def check_grounding(draft: str, blocks: Sequence[ContextBlock]) -> GroundingDecision:
    """Uma citação fica só quando o índice existe. Um telefone ausente reprova."""
    if _phone_outside_context(draft, blocks):
        return GroundingDecision(grounded=False, citations=())
    citations = _citations(draft, blocks)
    if not citations:
        return GroundingDecision(grounded=False, citations=())
    return GroundingDecision(grounded=True, citations=tuple(citations))


def _phone_outside_context(draft: str, blocks: Sequence[ContextBlock]) -> bool:
    context = _digits(_context_text(blocks))
    return any(_digits(match.group(0)) not in context for match in _PHONE_RE.finditer(draft))


def _citations(draft: str, blocks: Sequence[ContextBlock]) -> list[Citation]:
    by_index = {block.index: block for block in blocks}
    found: list[Citation] = []
    seen: set[int] = set()
    for match in _CITATION_RE.finditer(draft):
        index = int(match.group(1))
        block = by_index.get(index)
        if block is None or index in seen:
            continue
        seen.add(index)
        found.append(
            Citation(
                index=index,
                document_title=block.document_title,
                heading=block.heading,
                chunk_id=block.chunk_id,
            )
        )
    return found


def _context_text(blocks: Sequence[ContextBlock]) -> str:
    parts: list[str] = []
    for block in blocks:
        if block.heading:
            parts.append(block.heading)
        parts.append(block.content)
    return "\n".join(parts)


def _digits(value: str) -> str:
    return "".join(character for character in value if character.isdigit())
