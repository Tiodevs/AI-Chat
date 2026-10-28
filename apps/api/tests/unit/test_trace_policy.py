"""Cada política deixa sair só o permitido. Seção 18.4."""

import json
import os
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

from app.adapters.langsmith_tracing import (
    US_ENDPOINT,
    build_policy_clients,
    flush_clients,
    langsmith_api_url,
)
from app.core.config import Settings
from app.domain.pseudonym import subject_pseudonym
from app.domain.trace_policy import (
    DIGITS_MARKER,
    EMAIL_MARKER,
    PHONE_MARKER,
    ingestion_event,
    outgoing,
    registration_event_from_record,
    selected_metadata,
)

NAME = "Marina Costa"
EMAIL = "marina.costa@example.com"
PHONE = "(555) 014-2640"
NOTE = "protocolo 123456789012"
QUESTION = "Qual o horário de Marina Costa, marina.costa@example.com, (555) 014-2640?"
STABLE_UUID = "00000000-0000-4000-8000-000000000001"
SUBJECT = "ab" * 32
CI = Path(__file__).resolve().parents[4] / ".github" / "workflows" / "ci.yml"

_PAYLOAD = cast(
    dict[str, object],
    {
        "name": NAME,
        "email": EMAIL,
        "phone": PHONE,
        "note": NOTE,
        "standalone_question": QUESTION,
        "chunks": [{"content": "Ligue (555) 014-2600."}],
        "answer": "O horário é 11:00.",
        "outcome": "answered",
        "intent": "public_info",
        "conversation_id": STABLE_UUID,
        "subject": SUBJECT,
    },
)


def test_each_policy_projects_name_email_and_phone() -> None:
    full = outgoing("full", _PAYLOAD)
    masked = outgoing("masked", _PAYLOAD)
    hidden = outgoing("metadata_only", _PAYLOAD)

    assert full["name"] == NAME
    assert full["email"] == EMAIL_MARKER
    assert full["phone"] == PHONE_MARKER
    assert full["note"] == f"protocolo {DIGITS_MARKER}"
    assert NAME in str(full["standalone_question"])
    assert EMAIL_MARKER in str(full["standalone_question"])
    assert PHONE_MARKER in str(full["standalone_question"])
    assert full["conversation_id"] == STABLE_UUID
    assert full["subject"] == SUBJECT
    assert EMAIL not in json.dumps(full)
    assert PHONE not in json.dumps(full)
    assert "123456789012" not in json.dumps(full)

    assert "name" not in masked
    assert "email" not in masked
    assert "phone" not in masked
    assert "note" not in masked
    assert masked["outcome"] == "answered"
    assert NAME in str(masked["standalone_question"])
    assert EMAIL_MARKER in str(masked["standalone_question"])
    assert PHONE not in json.dumps(masked)
    assert EMAIL not in json.dumps(masked)

    assert hidden == {}


def test_metadata_drops_contact_fields_and_keeps_the_outcome() -> None:
    metadata = selected_metadata(
        {
            "name": NAME,
            "email": EMAIL,
            "phone": PHONE,
            "outcome": "refused",
            "intent": "medical_advice",
            "subject": SUBJECT,
            "conversation_id": STABLE_UUID,
            "confidence": None,
        }
    )
    rendered = json.dumps(metadata)
    assert metadata["outcome"] == "refused"
    assert metadata["intent"] == "medical_advice"
    assert metadata["subject"] == SUBJECT
    assert metadata["conversation_id"] == STABLE_UUID
    assert "name" not in metadata
    assert EMAIL not in rendered
    assert PHONE not in rendered
    assert NAME not in rendered


def test_registration_trace_drops_field_values() -> None:
    event = registration_event_from_record(
        {
            "field_names": ["full_name", "email"],
            "next_step": "awaiting_password",
            "input_tokens": 4,
            "output_tokens": 2,
            "values": {"name": NAME, "email": EMAIL, "phone": PHONE},
        },
        run_id=uuid4(),
    )
    rendered = json.dumps(
        {"inputs": event.inputs, "outputs": event.outputs, "metadata": event.metadata}
    )
    assert event.policy == "metadata_only"
    assert event.inputs == {}
    assert event.outputs == {}
    assert event.tags == ("registration",)
    assert event.metadata["field_names"] == ["full_name", "email"]
    assert event.metadata["next_step"] == "awaiting_password"
    assert EMAIL not in rendered
    assert PHONE not in rendered
    assert NAME not in rendered


def test_ingestion_trace_is_full_and_anonymized() -> None:
    event = ingestion_event(
        run_id=uuid4(),
        slug="02-visiting",
        body=f"A visita de {NAME} usa {EMAIL} e {PHONE}.",
    )
    rendered = json.dumps(event.inputs)
    assert event.policy == "full"
    assert event.tags == ("ingestion",)
    assert event.inputs["slug"] == "02-visiting"
    assert NAME in str(event.inputs["body"])
    assert EMAIL_MARKER in str(event.inputs["body"])
    assert PHONE_MARKER in str(event.inputs["body"])
    assert EMAIL not in rendered
    assert PHONE not in rendered


def test_clients_match_the_policy_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGSMITH_HIDE_INPUTS", "true")
    monkeypatch.setenv("LANGSMITH_HIDE_OUTPUTS", "true")
    clients = build_policy_clients(
        api_key="test-key",
        api_url="http://127.0.0.1:9",
        sampling_rate=1.0,
        auto_batch_tracing=False,
    )
    try:
        assert clients.full._hide_run_inputs(_PAYLOAD) == outgoing("full", _PAYLOAD)
        assert clients.masked._hide_run_inputs(_PAYLOAD) == outgoing("masked", _PAYLOAD)
        assert clients.metadata_only._hide_run_inputs(_PAYLOAD) == {}
        assert clients.metadata_only._hide_run_outputs(_PAYLOAD) == {}
        assert os.environ["LANGSMITH_HIDE_INPUTS"] == "true"
    finally:
        clients.close()


def test_empty_endpoint_uses_the_united_states() -> None:
    assert langsmith_api_url("") == US_ENDPOINT
    assert langsmith_api_url(US_ENDPOINT) == US_ENDPOINT


def test_pseudonym_changes_with_the_key() -> None:
    subject = uuid4()
    assert subject_pseudonym(subject, "one") == subject_pseudonym(subject, "one")
    assert subject_pseudonym(subject, "one") != subject_pseudonym(subject, "two")
    with pytest.raises(ValueError, match="pseudonym"):
        subject_pseudonym(subject, "")


def test_flush_records_the_call_and_ignores_a_failure() -> None:
    class Recorder:
        def __init__(self, fail: bool = False) -> None:
            self.calls = 0
            self.fail = fail

        def flush(self) -> None:
            self.calls += 1
            if self.fail:
                raise RuntimeError("down")

    healthy = Recorder()
    broken = Recorder(fail=True)
    flush_clients((healthy, broken))
    assert healthy.calls == 1
    assert broken.calls == 1


def test_standard_ci_does_not_read_a_langsmith_key() -> None:
    text = CI.read_text(encoding="utf-8")
    assert "LANGSMITH_API_KEY" not in text
    assert "langsmith" not in text.casefold()


def test_pytest_keeps_langsmith_tracing_off() -> None:
    assert os.environ["LANGSMITH_TRACING"] == "false"
    settings = Settings(_env_file=None, langsmith_tracing=False, langsmith_api_key="secret")
    from app.adapters.langsmith_tracing import feedback_sink_for

    sink = feedback_sink_for(settings)
    assert type(sink).__name__ == "NoopFeedbackSink"
