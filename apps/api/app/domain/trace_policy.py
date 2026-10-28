"""O que cada política de rastro deixa sair. Seção 18.4 e ADR-006."""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid4

TracePolicy = Literal["full", "masked", "metadata_only"]

EMAIL_MARKER = "[redacted-email]"
PHONE_MARKER = "[redacted-phone]"
DIGITS_MARKER = "[redacted-digits]"

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(
    r"(?<!\w)(?:\(\d{3}\)\s*\d{3}-\d{4}|\+\d[\d\s().-]{7,}\d|\d{3}[-.\s]\d{3}[-.\s]\d{4})(?!\w)"
)
_LONG_DIGITS_RE = re.compile(r"(?<!\d)\d{6,}(?!\d)")
_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_HEX_TOKEN_RE = re.compile(r"\b(?=[0-9a-fA-F]*[a-fA-F])[0-9a-fA-F]{16,}\b")
_SHIELD_RE = re.compile("\ue000(\\d+)\ue001")

_MASKED_KEYS = frozenset({"standalone_question", "chunks", "answer", "citations", "outcome"})
_METADATA_KEYS = frozenset(
    {
        "request_id",
        "trace_id",
        "app_version",
        "prompt_version",
        "outcome",
        "environment",
        "conversation_id",
        "subject",
        "intent",
        "confidence",
        "input_tokens",
        "output_tokens",
        "next_step",
        "field_names",
    }
)


@dataclass(frozen=True, slots=True)
class TraceMetadata:
    environment: str
    app_version: str
    conversation_id: str | None = None
    subject: str | None = None
    trace_id: str | None = None


@dataclass(frozen=True, slots=True)
class TraceEvent:
    name: str
    policy: TracePolicy
    run_id: UUID
    parent_run_id: UUID | None
    inputs: dict[str, object]
    outputs: dict[str, object]
    metadata: dict[str, object]
    tags: tuple[str, ...]


def anonymize_text(value: str) -> str:
    """Troca e-mail, telefone e dígitos longos. Preserva UUID e hash."""
    shields: list[str] = []

    def shield(match: re.Match[str]) -> str:
        shields.append(match.group(0))
        return f"\ue000{len(shields) - 1}\ue001"

    shielded = _UUID_RE.sub(shield, value)
    shielded = _HEX_TOKEN_RE.sub(shield, shielded)
    shielded = _EMAIL_RE.sub(EMAIL_MARKER, shielded)
    shielded = _PHONE_RE.sub(PHONE_MARKER, shielded)
    shielded = _LONG_DIGITS_RE.sub(DIGITS_MARKER, shielded)
    return _SHIELD_RE.sub(lambda match: shields[int(match.group(1))], shielded)


def anonymize_payload(payload: dict[str, object]) -> dict[str, object]:
    walked = _walk(payload)
    if isinstance(walked, dict):
        return walked
    return {}


def outgoing(policy: TracePolicy, payload: dict[str, object]) -> dict[str, object]:
    """O que sairia como entrada ou saída dessa política."""
    if policy == "metadata_only":
        return {}
    visible = payload
    if policy == "masked":
        visible = {key: payload[key] for key in _MASKED_KEYS if key in payload}
    return anonymize_payload(visible)


def selected_metadata(metadata: Mapping[str, object]) -> dict[str, object]:
    selected = {
        key: value for key, value in metadata.items() if key in _METADATA_KEYS and value is not None
    }
    return anonymize_payload(selected)


def question_traces(
    *,
    run_id: UUID,
    intent: str | None,
    confidence: float | None,
    outcome: str,
    standalone_question: str | None,
    chunks: Sequence[Mapping[str, object]],
    answer: str,
    citations: Sequence[Mapping[str, object]],
    prompt_version: str | None,
    input_tokens: int,
    output_tokens: int,
    classified: bool,
    rewrite_prompt_version: str | None,
    rewrite_input_tokens: int,
    rewrite_output_tokens: int,
    request_id: str,
    trace: TraceMetadata,
) -> tuple[TraceEvent, ...]:
    """Raiz da pergunta e, se houve classificação, o passo qa.rewrite."""
    public = intent == "public_info"
    policy: TracePolicy = "masked" if public else "metadata_only"
    shared = _shared_metadata(
        request_id=request_id,
        trace=trace,
        prompt_version=prompt_version,
        outcome=outcome,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    if public:
        inputs = outgoing(
            "masked",
            {
                "standalone_question": standalone_question or "",
                "chunks": [dict(chunk) for chunk in chunks],
            },
        )
        outputs = outgoing(
            "masked",
            {
                "answer": answer,
                "citations": [dict(citation) for citation in citations],
                "outcome": outcome,
            },
        )
    else:
        inputs = {}
        outputs = {}
    events = [
        TraceEvent(
            name="qa",
            policy=policy,
            run_id=run_id,
            parent_run_id=None,
            inputs=inputs,
            outputs=outputs,
            metadata=selected_metadata(shared),
            tags=("qa",),
        )
    ]
    if classified and intent is not None:
        events.append(
            TraceEvent(
                name="qa.rewrite",
                policy="metadata_only",
                run_id=uuid4(),
                parent_run_id=run_id,
                inputs={},
                outputs={},
                metadata=selected_metadata(
                    {
                        **shared,
                        "intent": intent,
                        "confidence": confidence,
                        "prompt_version": rewrite_prompt_version,
                        "input_tokens": rewrite_input_tokens,
                        "output_tokens": rewrite_output_tokens,
                    }
                ),
                tags=("qa",),
            )
        )
    return tuple(events)


def registration_event_from_record(
    record: Mapping[str, object],
    *,
    run_id: UUID,
) -> TraceEvent:
    """Só nomes de campos, próximo passo e tokens. Valores não entram."""
    names = record.get("field_names")
    field_names = (
        [item for item in names if isinstance(item, str)] if isinstance(names, list) else []
    )
    next_step = record.get("next_step")
    return TraceEvent(
        name="registration",
        policy="metadata_only",
        run_id=run_id,
        parent_run_id=None,
        inputs={},
        outputs={},
        metadata=selected_metadata(
            {
                "field_names": field_names,
                "next_step": next_step if isinstance(next_step, str) else None,
                "input_tokens": _count(record.get("input_tokens")),
                "output_tokens": _count(record.get("output_tokens")),
            }
        ),
        tags=("registration",),
    )


def ingestion_event(*, run_id: UUID, slug: str, body: str) -> TraceEvent:
    """Corpus público, depois do anonimizador. Política full."""
    return TraceEvent(
        name="ingestion",
        policy="full",
        run_id=run_id,
        parent_run_id=None,
        inputs=outgoing("full", {"slug": slug, "body": body}),
        outputs=outgoing("full", {"status": "ready"}),
        metadata=selected_metadata({"outcome": "ready"}),
        tags=("ingestion",),
    )


def _shared_metadata(
    *,
    request_id: str,
    trace: TraceMetadata,
    prompt_version: str | None,
    outcome: str,
    input_tokens: int,
    output_tokens: int,
) -> dict[str, object]:
    return {
        "request_id": request_id,
        "trace_id": trace.trace_id,
        "app_version": trace.app_version,
        "prompt_version": prompt_version,
        "outcome": outcome,
        "environment": trace.environment,
        "conversation_id": trace.conversation_id,
        "subject": trace.subject,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def _walk(value: object) -> object:
    if isinstance(value, str):
        return anonymize_text(value)
    if isinstance(value, dict):
        return {str(key): _walk(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_walk(item) for item in value]
    return value


def _count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value
