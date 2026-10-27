"""Diagnóstico da busca híbrida. Seção 6.3 do SDD."""

import argparse
import asyncio
import sys

from app.adapters.embedding_factory import build_embedding_provider
from app.core.config import Settings
from app.core.logging import configure_logging
from app.prompts.auth import DATABASE_URL_MISSING
from app.prompts.corpus import MISSING_EMBEDDING_KEY, NO_SEARCH_RESULTS, NO_SECTION
from app.repositories.retrieval import RetrievedChunk
from app.services.retrieval import RetrievalService


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Busca híbrida de diagnóstico.")
    parser.add_argument("question")
    args = parser.parse_args(argv)
    settings = Settings()
    configure_logging(settings.log_level)
    if not settings.database_url:
        print(DATABASE_URL_MISSING, file=sys.stderr)
        raise SystemExit(1)
    if settings.app_ai_adapter == "gemini" and not settings.gemini_api_key:
        print(MISSING_EMBEDDING_KEY, file=sys.stderr)
        raise SystemExit(1)
    hits = asyncio.run(_run(settings, args.question))
    print(format_hits(hits))


async def _run(settings: Settings, question: str) -> list[RetrievedChunk]:
    service = RetrievalService(
        settings.database_url,
        build_embedding_provider(settings),
        minimum_similarity=settings.retrieval_min_similarity,
    )
    return await service.search(question)


def format_hits(hits: list[RetrievedChunk]) -> str:
    if not hits:
        return NO_SEARCH_RESULTS
    lines = ["documento | título | seção | similaridade"]
    for hit in hits:
        section = hit.heading or NO_SECTION
        lines.append(
            f"{hit.document_slug} | {hit.document_title} | {section} | {hit.similarity:.4f}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    main()
