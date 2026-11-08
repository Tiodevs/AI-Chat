"""Escolhe o adaptador de embedding. Seção 17 do SDD.

Padrão Strategy da seção 6.2, como `chat_factory`. Quem usa: `build_ai_runtime` em
`app.core.container` (o embedding da pergunta, uma vez por processo), o serviço de documentos
do admin (um provedor novo por pedido, para a ingestão) e os scripts `seed`, `search`, `ask` e
`run_evals`.

| `APP_AI_ADAPTER` | Chave do Gemini | Provedor |
|---|---|---|
| `fake` | qualquer | `DeterministicEmbeddingProvider`, vetor por hash do texto |
| `demo` | qualquer | `LexicalEmbeddingProvider`, palavras em comum ficam próximas |
| `gemini` | vazia | `UnavailableEmbeddingProvider` |
| `gemini` | preenchida | `GeminiEmbeddingProvider` com `EMBEDDING_MODEL` |

Os vetores de um adaptador não servem a outro, e a semente, que pula os checksums iguais, não
os refaz sozinha quando o adaptador muda (seção 22.1).
"""

from app.adapters.deterministic_embedding import DeterministicEmbeddingProvider
from app.adapters.gemini_embedding import GeminiEmbeddingProvider
from app.adapters.lexical_embedding import LexicalEmbeddingProvider
from app.adapters.unavailable import UnavailableEmbeddingProvider
from app.core.config import Settings
from app.ports.embedding import EmbeddingProvider


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """O provedor de embedding da configuração, pela tabela do cabeçalho deste arquivo.

    Todos usam `EMBEDDING_DIMENSIONS`. O `fake` se apresenta com o nome do `EMBEDDING_MODEL`;
    o `demo`, sempre como `demo-lexical`.
    """
    if settings.app_ai_adapter == "fake":
        return DeterministicEmbeddingProvider(
            dimensions=settings.embedding_dimensions,
            model_name=settings.embedding_model,
        )
    if settings.app_ai_adapter == "demo":
        return LexicalEmbeddingProvider(
            dimensions=settings.embedding_dimensions,
            model_name="demo-lexical",
        )
    if not settings.gemini_api_key:
        return UnavailableEmbeddingProvider(
            model_name=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
        )
    return GeminiEmbeddingProvider(
        api_key=settings.gemini_api_key,
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
    )
