"""Escolhe o adaptador de embedding. Seção 17 do SDD."""

from app.adapters.deterministic_embedding import DeterministicEmbeddingProvider
from app.adapters.gemini_embedding import GeminiEmbeddingProvider
from app.core.config import Settings
from app.ports.embedding import EmbeddingProvider


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.app_ai_adapter == "fake":
        return DeterministicEmbeddingProvider(
            dimensions=settings.embedding_dimensions,
            model_name=settings.embedding_model,
        )
    return GeminiEmbeddingProvider(
        api_key=settings.gemini_api_key,
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
    )
