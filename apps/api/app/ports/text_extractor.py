"""Porta de extração de texto. Seção 7.3 do SDD."""

from typing import Protocol


class TextExtractor(Protocol):
    async def extract(self, data: bytes, media_type: str) -> str: ...
