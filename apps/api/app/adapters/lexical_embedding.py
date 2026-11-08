"""Embedding lexical do modo `demo`. Seções 17 e 21.1 do SDD.

Cada palavra, sem acento e em minúscula, cai numa dimensão por hash. Textos que dividem
palavras ficam próximos, então a busca do modo `demo` encontra o chunk do horário de visita
para a pergunta do horário de visita. Não é um modelo: serve à e2e da CI e à demonstração
local sem chave. O `DeterministicEmbeddingProvider` dos testes continua por hash do texto.

Implementa a porta `EmbeddingProvider`. Quem usa: `build_embedding_provider` com
`APP_AI_ADAPTER=demo`; o `DemoChatProvider` reaproveita `tokens` para classificar a pergunta.
Com este embedding, a e2e usa o piso de similaridade 0,3 (seção 17).
"""

import hashlib
import math
import re
import unicodedata

from app.models.vector import EMBEDDING_DIMENSIONS

# Palavras sem conteúdo e os prefixos da seção 8.3, que estão em todo texto embedado.
_STOPWORDS = frozenset(
    {
        "a", "ao", "aos", "as", "com", "da", "das", "de", "do", "dos", "e", "em", "ha",
        "na", "nas", "no", "nos", "o", "os", "ou", "para", "por", "que", "qual", "quais",
        "se", "sao", "um", "uma", "eu", "voce", "voces", "posso", "pode", "meu", "minha",
        "title", "text", "task", "question", "answering", "query",
    }
)
_WORD = re.compile(r"[a-z0-9]+")
# Raiz grosseira: "estacionar" e "estacionamento" viram "estaci". Basta para a demonstração.
_STEM = 6


def tokens(text: str) -> list[str]:
    """As palavras do texto em minúsculas e sem acento, fora as vazias e as de uma letra.

    A normalização NFKD separa a letra do acento, que sai por ser um caractere combinante.
    """
    folded = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(char for char in folded if not unicodedata.combining(char))
    return [word for word in _WORD.findall(plain) if word not in _STOPWORDS and len(word) > 1]


class LexicalEmbeddingProvider:
    """Vetores por palavra, sem rede. O mesmo texto dá sempre o mesmo vetor."""

    def __init__(
        self,
        dimensions: int = EMBEDDING_DIMENSIONS,
        model_name: str = "demo-lexical",
    ) -> None:
        self.dimensions = dimensions
        self.model_name = model_name

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Um vetor por texto, na ordem recebida."""
        return [self._vector(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        """O vetor da pergunta, pela mesma regra dos documentos."""
        return self._vector(text)

    def _vector(self, text: str) -> list[float]:
        """O vetor de palavras do texto, com norma 1.

        É o "hashing trick": os primeiros 4 bytes do SHA-256 da raiz da palavra escolhem a
        dimensão, e um bit do quinto byte escolhe o sinal, para colisões entre palavras
        diferentes se anularem em média. Um texto sem palavras vira o vetor da primeira
        dimensão, porque um vetor nulo não tem direção e a distância de cosseno com ele não é
        definida.
        """
        values = [0.0] * self.dimensions
        for word in tokens(text):
            digest = hashlib.sha256(word[:_STEM].encode()).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            values[index] += 1.0 if digest[4] % 2 == 0 else -1.0
        norm = math.sqrt(sum(value * value for value in values))
        if norm == 0:
            values[0] = 1.0
            return values
        return [value / norm for value in values]
