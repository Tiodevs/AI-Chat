"""Divisor de Markdown: títulos e depois blocos de 1.000 com sobreposição de 150. Seção 7.3."""

import re
from dataclasses import dataclass

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
_HEADING = re.compile(r"^(#{1,6})[ \t]+(.*\S)\s*$")


@dataclass(frozen=True, slots=True)
class TextChunk:
    heading: str | None
    content: str


def markdown_title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        match = _HEADING.match(line.strip())
        if match and match.group(1) == "#":
            return match.group(2).strip()
    return fallback


def split_markdown(
    markdown: str,
    *,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[TextChunk]:
    normalized = markdown.replace("\r\n", "\n").replace("\r", "\n")
    chunks: list[TextChunk] = []
    for heading, body in _sections(normalized):
        for piece in _split_recursive(body, chunk_size, overlap):
            content = piece.strip()
            if content:
                chunks.append(TextChunk(heading, content))
    return chunks


def _sections(markdown: str) -> list[tuple[str | None, str]]:
    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    for line in markdown.split("\n"):
        match = _HEADING.match(line)
        if match:
            sections.append((match.group(2).strip(), []))
            continue
        sections[-1][1].append(line)
    return [(heading, "\n".join(lines).strip()) for heading, lines in sections]


def _split_recursive(text: str, chunk_size: int, overlap: int) -> list[str]:
    if text == "":
        return []
    if len(text) <= chunk_size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            end = _preferred_end(text, start, end)
        if end <= start:
            end = min(start + max(chunk_size, 1), len(text))
        chunks.append(text[start:end])
        if end >= len(text):
            break
        next_start = end - overlap
        if next_start <= start:
            next_start = end
        start = next_start
    return chunks


def _preferred_end(text: str, start: int, end: int) -> int:
    window = text[start:end]
    for separator in ("\n\n", "\n", " "):
        index = window.rfind(separator)
        if index > 0:
            return start + index
    return end
