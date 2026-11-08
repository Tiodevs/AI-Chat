"""Extrai Markdown, texto e PDF num threadpool. Seção 7.3 do SDD.

Implementa a porta `TextExtractor` (`app.ports.text_extractor`). Quem usa: o
`IngestionService`, montado por `app.core.container` para o admin e pelo script `seed`. O
upload do admin confere o tipo de mídia antes de chegar aqui (NFR-10).
"""

import asyncio
from io import BytesIO

from pypdf import PdfReader

_TEXT_TYPES = frozenset({"text/markdown", "text/plain", "text/x-markdown"})


def extract_text(data: bytes, media_type: str) -> str:
    """O texto do arquivo, pelo tipo de mídia.

    Markdown e texto são decodificados como UTF-8; um byte inválido levanta
    `UnicodeDecodeError`. O texto de PDF vem do `pypdf`, página a página, e uma página sem
    texto entra vazia. Outro tipo levanta `ValueError`. A ingestão trata qualquer exceção
    como versão `failed` (seção 7.3).
    """
    if media_type in _TEXT_TYPES:
        return data.decode("utf-8")
    if media_type == "application/pdf":
        reader = PdfReader(BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    raise ValueError(media_type)


class FileTextExtractor:
    """A extração fora do loop de eventos, para um PDF grande não travar os outros pedidos."""

    async def extract(self, data: bytes, media_type: str) -> str:
        """Roda `extract_text` numa thread do threadpool com `asyncio.to_thread` (seção 6.4)."""
        return await asyncio.to_thread(extract_text, data, media_type)
