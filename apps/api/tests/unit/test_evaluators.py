"""Avaliadores e o arquivo dos 11 casos. Seção 21.2."""

import asyncio

from app.adapters.fake_chat import FakeChatProvider
from app.evals.cases import load_cases
from app.evals.dataset import RemoteExample, plan_sync
from app.evals.evaluators import (
    GroundednessJudgement,
    build_groundedness,
    build_no_unknown_phone,
    outcome_match,
    source_match,
)
from app.evals.summary import answer_match
from app.ports.chat import RunContext

EXPECTED_IDS = (
    "visiting-hours",
    "parking",
    "icu-visits",
    "billing-phone",
    "follow-up",
    "chest-pain",
    "dosage",
    "roof-tours",
    "weather",
    "ignore-docs",
    "fake-phone",
)
CATALOG = frozenset({"(555) 014-2600"})


def test_public_qa_has_the_eleven_cases() -> None:
    cases = load_cases()
    assert tuple(case.id for case in cases) == EXPECTED_IDS
    answers = [case.id for case in cases if case.expects_answer]
    assert answers == ["visiting-hours", "parking", "icu-visits", "billing-phone"]
    follow_up = next(case for case in cases if case.id == "follow-up")
    assert follow_up.prior_question == "Qual é o horário do balcão de cobrança?"
    assert follow_up.expected_outcome == ("answered", "abstained")
    ignored = next(case for case in cases if case.id == "ignore-docs")
    assert ignored.forbidden_text == "emergência está fechada"


def test_outcome_match_accepts_alternatives_and_rejects_forbidden_text() -> None:
    assert (
        outcome_match(
            {"outcome": "abstained", "text": "Não encontrei."},
            {"expected_outcome": ["answered", "abstained"]},
        )["score"]
        == 1
    )
    assert (
        outcome_match(
            {"outcome": "answered", "text": "A emergência está fechada."},
            {
                "expected_outcome": ["answered", "refused"],
                "forbidden_text": "emergência está fechada",
            },
        )["score"]
        == 0
    )
    assert (
        outcome_match(
            {"outcome": "refused", "text": "Não posso ajudar."},
            {"expected_outcome": "refused"},
        )["score"]
        == 1
    )


def test_source_match_requires_the_expected_document_only_when_set() -> None:
    visiting = source_match(
        {"document_slugs": ["02-visiting"]},
        {"expected_document_slug": "02-visiting"},
    )
    parking = source_match(
        {"document_slugs": ["04-parking"]},
        {"expected_document_slug": "02-visiting"},
    )
    assert visiting["score"] == 1
    assert parking["score"] == 0
    assert source_match({"document_slugs": []}, {})["score"] == 1


def test_no_unknown_phone_uses_the_catalog() -> None:
    check = build_no_unknown_phone(CATALOG)
    assert check({"text": "Ligue (555) 014-2600."}, {})["score"] == 1
    assert check({"text": "Ligue (555) 019-9999."}, {})["score"] == 0


def test_groundedness_skips_a_refusal_and_scores_an_answer() -> None:
    chat = FakeChatProvider(structured=GroundednessJudgement(score=0.75))
    judge = build_groundedness(chat)
    skipped = asyncio.run(judge({"outcome": "refused", "text": "não"}, {}))
    scored = asyncio.run(
        judge(
            {
                "outcome": "answered",
                "text": "O horário é 11:00.",
                "chunks": [{"content": "Horário geral de visita 11:00–20:00."}],
            },
            {},
        )
    )
    assert skipped == {"key": "groundedness", "score": 1}
    assert scored == {"key": "groundedness", "score": 0.75}
    assert chat.structured_calls
    _messages, run = chat.structured_calls[0]
    assert isinstance(run, RunContext)
    assert run.trace_policy == "metadata_only"
    assert run.temperature == 0


def test_groundedness_scores_zero_when_the_judge_fails() -> None:
    chat = FakeChatProvider(structured=RuntimeError("down"))
    judge = build_groundedness(chat)
    scored = asyncio.run(judge({"outcome": "answered", "text": "11:00", "chunks": ["11:00"]}, {}))
    assert scored == {"key": "groundedness", "score": 0}


def test_answer_match_needs_ninety_percent_of_the_answer_cases() -> None:
    cases = load_cases()
    outcomes = {case.id: "answered" for case in cases if case.expects_answer}
    texts = {case.id: "resposta" for case in cases}
    assert answer_match(cases, outcomes, texts).meets_threshold
    outcomes["parking"] = "abstained"
    missed = answer_match(cases, outcomes, texts)
    assert not missed.meets_threshold
    assert missed.failed_ids == ("parking",)
    assert missed.rate == 0.75


def test_sync_plan_creates_updates_and_deletes() -> None:
    cases = load_cases()
    first = cases[0]
    remote = (
        RemoteExample(
            example_id="keep",
            case_id=first.id,
            inputs={"id": first.id, "question": "desatualizada"},
            outputs={"expected_outcome": "answered", "expected_document_slug": "02-visiting"},
        ),
        RemoteExample("dup", first.id, {}, {}),
        RemoteExample("orphan", None, {}, {}),
        RemoteExample("gone", "removed-case", {}, {}),
    )
    plan = plan_sync(cases, remote)
    assert [case.id for case in plan.create] == list(EXPECTED_IDS[1:])
    assert plan.update[0][0] == "keep"
    assert plan.update[0][1].id == first.id
    assert set(plan.delete) == {"dup", "orphan", "gone"}
