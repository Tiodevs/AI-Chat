"""Casos de evals/public_qa.jsonl. Seção 21.2 do SDD."""

import json
from dataclasses import dataclass
from pathlib import Path

DATASET_NAME = "atrium-public-qa"
ANSWER_MATCH_THRESHOLD = 0.9


@dataclass(frozen=True, slots=True)
class EvalCase:
    id: str
    question: str
    expected_outcome: tuple[str, ...]
    expected_document_slug: str | None
    prior_question: str | None = None
    forbidden_text: str | None = None

    @property
    def expects_answer(self) -> bool:
        return self.expected_outcome == ("answered",)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def cases_path() -> Path:
    return repo_root() / "evals" / "public_qa.jsonl"


def catalog_path() -> Path:
    return repo_root() / "docs" / "sdd" / "corpus.md"


def load_cases(path: Path | None = None) -> tuple[EvalCase, ...]:
    source = cases_path() if path is None else path
    cases: list[EvalCase] = []
    seen: set[str] = set()
    for line_number, raw in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError(f"line {line_number} is not an object")
        case = _case(payload, line_number)
        if case.id in seen:
            raise ValueError(f"duplicate case {case.id}")
        seen.add(case.id)
        cases.append(case)
    if not cases:
        raise ValueError("eval file is empty")
    return tuple(cases)


def example_inputs(case: EvalCase) -> dict[str, object]:
    payload: dict[str, object] = {"id": case.id, "question": case.question}
    if case.prior_question:
        payload["prior_question"] = case.prior_question
    return payload


def example_outputs(case: EvalCase) -> dict[str, object]:
    outcome: object = (
        case.expected_outcome[0] if len(case.expected_outcome) == 1 else list(case.expected_outcome)
    )
    payload: dict[str, object] = {"expected_outcome": outcome}
    if case.expected_document_slug:
        payload["expected_document_slug"] = case.expected_document_slug
    if case.forbidden_text:
        payload["forbidden_text"] = case.forbidden_text
    return payload


def _case(payload: dict[str, object], line_number: int) -> EvalCase:
    identifier = payload.get("id")
    question = payload.get("question")
    if not isinstance(identifier, str) or not identifier:
        raise ValueError(f"line {line_number} needs an id")
    if not isinstance(question, str) or not question.strip():
        raise ValueError(f"line {line_number} needs a question")
    prior = payload.get("prior_question")
    forbidden = payload.get("forbidden_text")
    slug = payload.get("expected_document_slug")
    return EvalCase(
        id=identifier,
        question=question,
        expected_outcome=_outcomes(payload.get("expected_outcome"), line_number),
        expected_document_slug=slug if isinstance(slug, str) and slug else None,
        prior_question=prior if isinstance(prior, str) and prior else None,
        forbidden_text=forbidden if isinstance(forbidden, str) and forbidden else None,
    )


def _outcomes(value: object, line_number: int) -> tuple[str, ...]:
    if isinstance(value, str) and value:
        return (value,)
    if isinstance(value, list) and value and all(isinstance(item, str) and item for item in value):
        return tuple(value)
    raise ValueError(f"line {line_number} needs expected_outcome")
