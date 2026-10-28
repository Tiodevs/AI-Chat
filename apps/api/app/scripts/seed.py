"""Semeia o corpus fictício. Seções 6.4 e 7.3 do SDD."""

import asyncio
import sys
from pathlib import Path

from app.adapters.embedding_factory import build_embedding_provider
from app.adapters.langsmith_tracing import tracer_for
from app.adapters.text_extractor import FileTextExtractor
from app.core.config import Settings
from app.core.logging import configure_logging
from app.domain.errors import DomainError
from app.ports.tracing import NullTracer
from app.prompts.auth import DATABASE_URL_MISSING
from app.prompts.corpus import MISSING_EMBEDDING_KEY, seed_message
from app.services.ingestion import IngestionService
from app.services.seed import SeedReport, SeedService


def main(argv: list[str] | None = None) -> None:
    del argv
    settings = Settings()
    configure_logging(settings.log_level)
    if not settings.database_url:
        print(DATABASE_URL_MISSING, file=sys.stderr)
        raise SystemExit(1)
    if settings.app_ai_adapter == "gemini" and not settings.gemini_api_key:
        print(MISSING_EMBEDDING_KEY, file=sys.stderr)
        raise SystemExit(1)
    try:
        report = asyncio.run(_run(settings))
    except DomainError as exc:
        print(exc.message, file=sys.stderr)
        raise SystemExit(1) from exc
    print(seed_message(report.embedded))


async def _run(settings: Settings) -> SeedReport:
    ingestion = IngestionService(
        settings.database_url,
        build_embedding_provider(settings),
        FileTextExtractor(),
        tracer=tracer_for(settings) or NullTracer(),
    )
    service = SeedService(settings.database_url, ingestion, default_corpus_dir())
    return await service.run()


def default_corpus_dir() -> Path:
    return Path(__file__).resolve().parents[4] / "content" / "corpus"


if __name__ == "__main__":
    main()
