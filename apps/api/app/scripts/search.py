"""Diagnóstico da busca híbrida. Seção 6.3 do SDD.

Uso: `python -m app.scripts.search "Qual é o horário de visita?"`, em `apps/api`.

Ferramenta de desenvolvimento da Etapa 3.3: roda só a recuperação da seção 8.4, sem o modelo de
chat, e imprime documento, título, seção e similaridade dos até 6 chunks que passam no piso
`RETRIEVAL_MIN_SIMILARITY`, na ordem da fusão. Só lê o banco.

Precisa de `DATABASE_URL`. Com `APP_AI_ADAPTER=gemini`, precisa também de `GEMINI_API_KEY`
para embedar a pergunta. Com `fake` ou `demo`, usa o embedding desse adaptador, que só encontra
algo num corpus semeado com o mesmo adaptador.
"""

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
    """Lê a pergunta, confere o ambiente e imprime a tabela dos chunks encontrados."""
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
    """A busca do `RetrievalService`, que acrescenta o prefixo da seção 8.3 à pergunta."""
    service = RetrievalService(
        settings.database_url,
        build_embedding_provider(settings),
        minimum_similarity=settings.retrieval_min_similarity,
    )
    return await service.search(question)


def format_hits(hits: list[RetrievedChunk]) -> str:
    """Uma linha por chunk, com a similaridade em 4 casas, ou o aviso de nenhum resultado."""
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
