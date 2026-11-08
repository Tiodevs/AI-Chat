"""Porta de extração de texto. Seção 7.3 do SDD.

Camada de portas. `IngestionService` extrai o texto de cada versão nova antes de dividir em
chunks. O adaptador é `FileTextExtractor` (`app/adapters/text_extractor.py`): Markdown e texto
como UTF-8, PDF pelo `pypdf`, numa thread separada para não travar o loop de eventos
(seção 6.4).
"""

from typing import Protocol


class TextExtractor(Protocol):
    """Lê o texto de um arquivo enviado."""

    async def extract(self, data: bytes, media_type: str) -> str:
        """Texto do arquivo conforme `media_type`.

        Levanta erro num arquivo ilegível ou de tipo desconhecido; a ingestão marca a versão
        como `failed` com a mensagem `EXTRACT_FAILED`.
        """
        ...
