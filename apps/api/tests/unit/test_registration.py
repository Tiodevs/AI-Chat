"""Máquina, lista de permissão e conclusão do cadastro. Seções 7.2, 8.5 e 10.2."""

from datetime import UTC, datetime

import pytest

from app.domain.fields import (
    TOOL_KEYS,
    FieldIssue,
    read_tool_arguments,
    set_fields_parameters,
)
from app.domain.legal import LEGAL_DOCUMENT_VERSION
from app.domain.registration import (
    Acceptance,
    FieldSet,
    Status,
    Step,
    TranscriptItem,
    apply_collected,
    decide_next,
    draft_member,
    mark_password_set,
    new_machine,
    reject_review,
)

NOW = datetime(2026, 10, 28, 3, 0, tzinfo=UTC)
TERMS = Acceptance(
    accept_terms=True,
    document_version=LEGAL_DOCUMENT_VERSION,
    age_18_plus=True,
    profile_personalization=False,
    quality_improvement=False,
)


def test_registration_tool_rejects_role_password_and_consents() -> None:
    properties = set_fields_parameters()["properties"]
    assert isinstance(properties, dict)
    assert set(properties) == TOOL_KEYS
    assert "role" not in properties
    assert "password" not in properties

    kept = new_machine()
    for extra in (
        {"role": "admin"},
        {"password": "correct-horse-1"},
        {"profile_personalization": True},
        {"age_18_plus": True},
        {"accept_terms": True},
        {"consents": ["terms_and_privacy_notice"]},
    ):
        read = read_tool_arguments({"full_name": "Ana Costa", **extra})
        assert read.rejected is True
        assert read.values == {}
        applied = apply_collected(kept, read)
        assert applied.fields.full_name is None
        assert applied.status == Status.COLLECTING_REQUIRED


def test_registration_transcript_serializer_has_no_password_field() -> None:
    assert set(TranscriptItem.model_fields) == {"role", "text", "created_at"}
    loaded = TranscriptItem.model_validate(
        {
            "role": "user",
            "text": "Ana Costa",
            "created_at": NOW.isoformat(),
            "password": "senha-que-nao-pode-vazar",
        }
    )
    dumped = loaded.model_dump()
    assert set(dumped) == {"role", "text", "created_at"}
    assert "senha-que-nao-pode-vazar" not in loaded.model_dump_json()


def test_registration_machine_skips_optionals_and_returns_to_correction() -> None:
    machine = decide_next(
        apply_collected(
            new_machine(),
            read_tool_arguments({"full_name": "Ana Costa", "email": "ana@example.com"}),
        )
    )
    assert machine.status == Status.COLLECTING_OPTIONAL
    assert machine.next_step == Step.PHONE
    for expected in (Step.VISITOR_TYPE, Step.VISIT_REASON, Step.PASSWORD):
        machine = decide_next(apply_collected(machine, read_tool_arguments({"skip_current": True})))
        assert machine.next_step == expected
    assert machine.status == Status.AWAITING_PASSWORD
    reviewed = mark_password_set(machine)
    assert reviewed is not None
    assert reviewed.status == Status.AWAITING_REVIEW
    correcting = reject_review(reviewed)
    assert correcting is not None
    assert correcting.status == Status.COLLECTING_REQUIRED
    assert correcting.correcting is True
    assert correcting.next_step == Step.FULL_NAME
    assert correcting.fields.full_name == "Ana Costa"


@pytest.mark.parametrize(
    ("acceptance", "code"),
    [
        (Acceptance(False, LEGAL_DOCUMENT_VERSION, True, False, False), "accept_terms"),
        (Acceptance(True, "2000-01-01.1", True, False, False), "accept_terms"),
        (Acceptance(True, LEGAL_DOCUMENT_VERSION, False, False, False), "age_18_plus"),
    ],
)
def test_registration_draft_requires_terms_and_age(acceptance: Acceptance, code: str) -> None:
    result = draft_member(
        _ready_fields(),
        acceptance,
        expected_version=LEGAL_DOCUMENT_VERSION,
        password_ready=True,
    )
    assert isinstance(result, tuple)
    assert FieldIssue(code, "required") in result


def test_registration_draft_discards_sensitive_fields_without_personalization() -> None:
    fields = FieldSet(
        full_name="Ana Costa",
        email="ana@example.com",
        phone="5550142600",
        visitor_type="patient",
        visit_reason="own_appointment",
    )
    refused = draft_member(
        fields,
        TERMS,
        expected_version=LEGAL_DOCUMENT_VERSION,
        password_ready=True,
    )
    assert not isinstance(refused, tuple)
    assert refused.visitor_type is None
    assert refused.visit_reason is None
    assert refused.phone == "5550142600"
    assert all(grant.purpose != "profile_personalization" for grant in refused.consents)

    granted = draft_member(
        fields,
        Acceptance(True, LEGAL_DOCUMENT_VERSION, True, True, True),
        expected_version=LEGAL_DOCUMENT_VERSION,
        password_ready=True,
    )
    assert not isinstance(granted, tuple)
    assert granted.visitor_type == "patient"
    assert granted.visit_reason == "own_appointment"
    purposes = {grant.purpose for grant in granted.consents}
    assert purposes == {
        "terms_and_privacy_notice",
        "age_18_plus",
        "profile_personalization",
        "quality_improvement",
    }
    assert {grant.document_version for grant in granted.consents} == {LEGAL_DOCUMENT_VERSION}


def _ready_fields() -> FieldSet:
    return FieldSet(
        full_name="Ana Costa",
        email="ana@example.com",
        phone_skipped=True,
        visitor_type_skipped=True,
        visit_reason_skipped=True,
    )
