"""Roda o pipeline de perguntas com o Gemini de desenvolvimento. Seção 6.3 do SDD."""

import argparse
import asyncio
import sys
from uuid import uuid4

from app.adapters.chat_factory import build_chat_provider
from app.adapters.clock import SystemClock
from app.adapters.embedding_factory import build_embedding_provider
from app.core.config import Settings
from app.core.logging import configure_logging
from app.domain.grounding import Citation
from app.prompts.auth import DATABASE_URL_MISSING
from app.prompts.qa import ASK_NEEDS_GEMINI, NO_CITATIONS, NO_SECTION
from app.services.budget import PostgresTokenBudget
from app.services.question import QuestionService
from app.services.retrieval import RetrievalService
from app.workflows.qa import QaResult, QaWorkflow


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Pipeline de perguntas, sem HTTP.")
    parser.add_argument("question")
    args = parser.parse_args(argv)
    settings = Settings()
    configure_logging(settings.log_level)
    if not settings.database_url:
        print(DATABASE_URL_MISSING, file=sys.stderr)
        raise SystemExit(1)
    if settings.app_ai_adapter != "gemini" or not settings.gemini_api_key:
        print(ASK_NEEDS_GEMINI, file=sys.stderr)
        raise SystemExit(1)
    result = asyncio.run(_run(settings, args.question))
    print(format_ask_result(result))


async def _run(settings: Settings, question: str) -> QaResult:
    embeddings = build_embedding_provider(settings)
    service = QuestionService(
        QaWorkflow(
            build_chat_provider(settings),
            embeddings,
            RetrievalService(
                settings.database_url,
                embeddings,
                minimum_similarity=settings.retrieval_min_similarity,
            ),
            minimum_similarity=settings.retrieval_min_similarity,
        ),
        PostgresTokenBudget(
            settings.database_url,
            SystemClock(),
            settings.llm_daily_token_budget,
        ),
    )
    return await service.ask(question, request_id=str(uuid4()))


def format_ask_result(result: QaResult) -> str:
    lines = [result.outcome.value]
    if not result.citations:
        lines.append(NO_CITATIONS)
    else:
        lines.extend(_citation_line(citation) for citation in result.citations)
    lines.append(result.text)
    return "\n".join(lines)


def _citation_line(citation: Citation) -> str:
    heading = citation.heading or NO_SECTION
    return f"{citation.index} | {citation.document_title} | {heading}"


if __name__ == "__main__":
    main()
