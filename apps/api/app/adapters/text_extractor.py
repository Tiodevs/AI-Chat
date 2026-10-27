"""Extrai Markdown, texto e PDF num threadpool. Seção 7.3 do SDD."""

import asyncio
from io import BytesIO

from pypdf import PdfReader

_TEXT_TYPES = frozenset({"text/markdown", "text/plain", "text/x-markdown"})


def extract_text(data: bytes, media_type: str) -> str:
    if media_type in _TEXT_TYPES:
        return data.decode("utf-8")
    if media_type == "application/pdf":
        reader = PdfReader(BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    raise ValueError(media_type)


class FileTextExtractor:
    async def extract(self, data: bytes, media_type: str) -> str:
        return await asyncio.to_thread(extract_text, data, media_type)
