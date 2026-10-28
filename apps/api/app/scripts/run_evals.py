"""Roda o conjunto público no LangSmith. Seção 21.2 do SDD."""

import asyncio
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from uuid import uuid4

from langsmith import Client, aevaluate

from app.adapters.chat_factory import build_chat_provider
from app.adapters.embedding_factory import build_embedding_provider
from app.adapters.langsmith_tracing import langsmith_api_url
from app.core.config import Settings
from app.core.logging import configure_logging
from app.domain.phones import phones_in
from app.domain.trace_policy import anonymize_payload
from app.evals.cases import (
    DATASET_NAME,
    EvalCase,
    catalog_path,
    example_outputs,
    load_cases,
)
from app.evals.evaluators import (
    build_groundedness,
    build_no_unknown_phone,
    outcome_match,
    source_match,
)
from app.evals.summary import answer_match, render_summary
from app.prompts.auth import DATABASE_URL_MISSING
from app.prompts.qa import ASK_NEEDS_GEMINI, GENERATE_PROMPT_VERSION, REWRITE_PROMPT_VERSION
from app.services.retrieval import RetrievalService
from app.workflows.qa import ConversationTurn, QaResult, QaWorkflow


def main() -> None:
    settings = Settings()
    configure_logging(settings.log_level)
    if not settings.database_url:
        print(DATABASE_URL_MISSING, file=sys.stderr)
        raise SystemExit(1)
    if settings.app_ai_adapter != "gemini" or not settings.gemini_api_key:
        print(ASK_NEEDS_GEMINI, file=sys.stderr)
        raise SystemExit(1)
    if not settings.langsmith_api_key:
        print("Defina LANGSMITH_API_KEY.", file=sys.stderr)
        raise SystemExit(1)
    summary = asyncio.run(_run(settings))
    print(summary)
    destination = os.environ.get("EVAL_SUMMARY_PATH")
    if destination:
        Path(destination).write_text(summary, encoding="utf-8")


async def _run(settings: Settings) -> str:
    cases = load_cases()
    catalog = frozenset(phones_in(catalog_path().read_text(encoding="utf-8")))
    chat = build_chat_provider(settings)
    embeddings = build_embedding_provider(settings)
    workflow = QaWorkflow(
        chat,
        embeddings,
        RetrievalService(
            settings.database_url,
            embeddings,
            minimum_similarity=settings.retrieval_min_similarity,
        ),
        minimum_similarity=settings.retrieval_min_similarity,
    )
    recorded: list[tuple[str, dict[str, object]]] = []

    async def target(inputs: dict[str, object]) -> dict[str, object]:
        case_id = inputs.get("id")
        identifier = case_id if isinstance(case_id, str) else "unknown"
        prior = inputs.get("prior_question")
        history: tuple[ConversationTurn, ...] = ()
        if isinstance(prior, str) and prior:
            prior_result = await workflow.run(
                prior,
                history=(),
                visitor_type=None,
                request_id=f"eval-prior-{identifier}-{uuid4()}",
            )
            history = (
                ConversationTurn(role="user", content=prior),
                ConversationTurn(role="assistant", content=prior_result.text),
            )
        question = inputs.get("question")
        if not isinstance(question, str):
            raise ValueError("question")
        result = await workflow.run(
            question,
            history=history,
            visitor_type=None,
            request_id=f"eval-{identifier}-{uuid4()}",
        )
        output = _output(result)
        recorded.append((identifier, output))
        return output

    client = Client(
        api_key=settings.langsmith_api_key,
        api_url=langsmith_api_url(settings.langsmith_endpoint),
        workspace_id=settings.langsmith_workspace_id or None,
        anonymizer=anonymize_payload,
        hide_inputs=False,
        hide_outputs=False,
        tracing_sampling_rate=settings.langsmith_tracing_sampling_rate,
    )
    experiment_name: str | None = None
    experiment_url: str | None = None
    baseline: str | None = None
    try:
        evaluators: list[Any] = [
            outcome_match,
            source_match,
            build_no_unknown_phone(catalog),
            build_groundedness(chat),
        ]
        results = await aevaluate(
            target,
            data=DATASET_NAME,
            evaluators=evaluators,
            experiment_prefix=f"atrium-{GENERATE_PROMPT_VERSION}",
            metadata={
                "prompt_version": GENERATE_PROMPT_VERSION,
                "rewrite_prompt_version": REWRITE_PROMPT_VERSION,
                "git_sha": os.environ.get("GITHUB_SHA", ""),
                "git_ref": os.environ.get("GITHUB_REF_NAME", "local"),
            },
            # Uma de cada vez: rajadas abrem o circuito do Gemini em 429.
            max_concurrency=1,
            client=client,
            description="Conjunto público do Atrium.",
        )
        experiment_name = results.experiment_name
        experiment_url = results.url
        baseline = _baseline(client, experiment_name)
    finally:
        client.flush()
        client.close()
    return _summary(cases, recorded, experiment_name, experiment_url, baseline)


def _summary(
    cases: Sequence[EvalCase],
    recorded: Sequence[tuple[str, dict[str, object]]],
    experiment_name: str | None,
    experiment_url: str | None,
    baseline: str | None,
) -> str:
    by_id = {case_id: output for case_id, output in recorded}
    outcomes = {case.id: _text(by_id.get(case.id, {}).get("outcome")) for case in cases}
    texts = {case.id: _text(by_id.get(case.id, {}).get("text")) for case in cases}
    rows: list[tuple[str, str, str, int]] = []
    for case in cases:
        output = by_id.get(case.id, {})
        score = outcome_match(output, example_outputs(case))["score"]
        rows.append(
            (
                case.id,
                ", ".join(case.expected_outcome),
                outcomes[case.id] or "ausente",
                1 if score == 1 else 0,
            )
        )
    match = answer_match(cases, outcomes, texts)
    return render_summary(
        prompt_version=GENERATE_PROMPT_VERSION,
        match=match,
        rows=rows,
        experiment_name=experiment_name,
        experiment_url=experiment_url,
        baseline=baseline,
    )


def _output(result: QaResult) -> dict[str, object]:
    by_chunk = {chunk.chunk_id: chunk for chunk in result.chunks}
    slugs: list[str] = []
    cited: list[dict[str, str]] = []
    for citation in result.citations:
        chunk = by_chunk.get(citation.chunk_id)
        if chunk is None:
            continue
        slugs.append(chunk.document_slug)
        cited.append({"document_slug": chunk.document_slug, "content": chunk.content})
    return {
        "outcome": result.outcome.value,
        "text": result.text,
        "document_slugs": slugs,
        "chunks": cited,
    }


def _baseline(client: Client, current_name: str) -> str | None:
    try:
        projects = client.list_projects(
            reference_dataset_name=DATASET_NAME,
            metadata={"git_ref": "main"},
            limit=10,
        )
    except Exception:
        return None
    names = [
        project.name
        for project in projects
        if getattr(project, "name", None) and project.name != current_name
    ]
    if not names:
        return None
    return names[0]


def _text(value: object) -> str:
    if isinstance(value, str):
        return value
    return ""


if __name__ == "__main__":
    main()
