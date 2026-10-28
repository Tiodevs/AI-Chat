"""Quatro avaliadores. Seção 21.2 do SDD."""

import unicodedata
from collections.abc import Callable, Coroutine, Sequence
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.domain.phones import unknown_phones
from app.ports.chat import ChatProvider, Message, RunContext
from app.prompts.evals import (
    GROUNDEDNESS_INSTRUCTIONS,
    GROUNDEDNESS_PROMPT_VERSION,
    SCORE_DESCRIPTION,
)


class GroundednessJudgement(BaseModel):
    model_config = ConfigDict(extra="ignore")

    score: float = Field(ge=0, le=1, description=SCORE_DESCRIPTION)


def outcome_match(
    outputs: dict[str, object],
    reference_outputs: dict[str, object],
) -> dict[str, object]:
    expected = _expected_outcomes(reference_outputs.get("expected_outcome"))
    actual = outputs.get("outcome")
    raw_text = outputs.get("text")
    text = raw_text if isinstance(raw_text, str) else ""
    forbidden = reference_outputs.get("forbidden_text")
    forbidden_text = forbidden if isinstance(forbidden, str) else None
    matched = isinstance(actual, str) and outcome_matches(
        expected,
        actual,
        text,
        forbidden_text,
    )
    return {"key": "outcome_match", "score": 1 if matched else 0}


def source_match(
    outputs: dict[str, object],
    reference_outputs: dict[str, object],
) -> dict[str, object]:
    expected = reference_outputs.get("expected_document_slug")
    if not isinstance(expected, str) or not expected:
        return {"key": "source_match", "score": 1}
    slugs = outputs.get("document_slugs")
    found = slugs if isinstance(slugs, list) else []
    return {"key": "source_match", "score": 1 if expected in found else 0}


def build_no_unknown_phone(
    catalog: frozenset[str],
) -> Callable[[dict[str, object], dict[str, object]], dict[str, object]]:
    def no_unknown_phone(
        outputs: dict[str, object],
        reference_outputs: dict[str, object],
    ) -> dict[str, object]:
        del reference_outputs
        text = outputs.get("text")
        unknown = unknown_phones(text if isinstance(text, str) else "", catalog)
        return {"key": "no_unknown_phone", "score": 0 if unknown else 1}

    return no_unknown_phone


def build_groundedness(
    chat: ChatProvider,
) -> Callable[..., Coroutine[Any, Any, dict[str, object]]]:
    async def groundedness(
        outputs: dict[str, object],
        reference_outputs: dict[str, object],
    ) -> dict[str, object]:
        del reference_outputs
        if outputs.get("outcome") != "answered":
            return {"key": "groundedness", "score": 1}
        chunks = _chunk_text(outputs.get("chunks"))
        raw_answer = outputs.get("text")
        answer = raw_answer if isinstance(raw_answer, str) else ""
        if not chunks or not answer.strip():
            return {"key": "groundedness", "score": 0}
        try:
            judgement = await chat.complete_structured(
                [
                    Message(role="system", content=GROUNDEDNESS_INSTRUCTIONS),
                    Message(role="user", content=_judge_user(chunks, answer)),
                ],
                GroundednessJudgement,
                RunContext(
                    run_id=uuid4(),
                    request_id="eval-groundedness",
                    prompt_version=GROUNDEDNESS_PROMPT_VERSION,
                    trace_policy="metadata_only",
                    tags=("qa",),
                    temperature=0.0,
                ),
            )
        except Exception:
            return {"key": "groundedness", "score": 0}
        return {"key": "groundedness", "score": judgement.score}

    return groundedness


def outcome_matches(
    expected: tuple[str, ...],
    actual: str,
    text: str,
    forbidden_text: str | None,
) -> bool:
    if actual not in expected:
        return False
    return not (forbidden_text and _fold(forbidden_text) in _fold(text))


def _expected_outcomes(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list):
        return tuple(item for item in value if isinstance(item, str))
    return ()


def _chunk_text(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    found: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            found.append(item)
        elif isinstance(item, dict):
            content = item.get("content")
            if isinstance(content, str) and content.strip():
                found.append(content)
    return found


def _judge_user(chunks: Sequence[str], answer: str) -> str:
    rendered = "\n\n".join(
        f'<trecho indice="{index}">\n{content}\n</trecho>'
        for index, content in enumerate(chunks, start=1)
    )
    return f"Trechos:\n{rendered}\n\nResposta:\n{answer}"


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.casefold())
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")
