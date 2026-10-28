"""Máquina de estados do cadastro. O modelo não conclui a conta. Seção 7.2."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from app.domain.auth import (
    RateDecision,
    email_is_valid,
    fixed_window_start,
    retry_after_seconds,
)
from app.domain.fields import (
    EDITABLE_FIELDS,
    OPTIONAL_FIELDS,
    VISIT_REASONS,
    VISITOR_TYPES,
    FieldIssue,
    ToolRead,
    name_is_valid,
    phone_is_valid,
    validate_field,
)

MEMBER_ROLE = "member"
REGISTRATION_TTL = timedelta(hours=24)
REGISTRATION_IP_LIMIT = 20
REGISTRATION_WINDOW = timedelta(hours=1)
REGISTRATION_IP_PURPOSE = "registration_ip"
MAX_MESSAGE_CHARS = 1000


class Status(StrEnum):
    COLLECTING_REQUIRED = "collecting_required"
    COLLECTING_OPTIONAL = "collecting_optional"
    AWAITING_PASSWORD = "awaiting_password"
    AWAITING_REVIEW = "awaiting_review"
    AWAITING_ACCEPTANCE = "awaiting_acceptance"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class Step(StrEnum):
    FULL_NAME = "full_name"
    EMAIL = "email"
    PHONE = "phone"
    VISITOR_TYPE = "visitor_type"
    VISIT_REASON = "visit_reason"
    PASSWORD = "password"
    REVIEW = "review"
    ACCEPTANCE = "acceptance"


class Path(StrEnum):
    CHAT = "chat"
    FORM = "form"


class Purpose(StrEnum):
    TERMS = "terms_and_privacy_notice"
    AGE = "age_18_plus"
    PERSONALIZATION = "profile_personalization"
    QUALITY = "quality_improvement"


class ConsentSource(StrEnum):
    CHAT = "chat"
    FORM = "form"
    ACCOUNT = "account"


STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{item.value}'" for item in Status) + ")"
PATH_CHECK_SQL = "path IN (" + ", ".join(f"'{item.value}'" for item in Path) + ")"
PURPOSE_CHECK_SQL = "purpose IN (" + ", ".join(f"'{item.value}'" for item in Purpose) + ")"
SOURCE_CHECK_SQL = "source IN (" + ", ".join(f"'{item.value}'" for item in ConsentSource) + ")"

_COLLECTING = frozenset({Status.COLLECTING_REQUIRED, Status.COLLECTING_OPTIONAL})
_REVIEWABLE = frozenset(
    {Status.AWAITING_REVIEW, Status.AWAITING_ACCEPTANCE, Status.AWAITING_PASSWORD}
)


@dataclass(frozen=True, slots=True)
class FieldSet:
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    phone_skipped: bool = False
    visitor_type: str | None = None
    visitor_type_skipped: bool = False
    visit_reason: str | None = None
    visit_reason_skipped: bool = False


@dataclass(frozen=True, slots=True)
class Machine:
    status: Status
    fields: FieldSet
    password_set: bool
    correcting: bool
    field_errors: tuple[FieldIssue, ...]
    next_step: Step


@dataclass(frozen=True, slots=True)
class PublicFields:
    full_name: str | None
    email: str | None
    phone: str | None
    visitor_type: str | None
    visit_reason: str | None


@dataclass(frozen=True, slots=True)
class Acceptance:
    accept_terms: bool
    document_version: str
    age_18_plus: bool
    profile_personalization: bool
    quality_improvement: bool


@dataclass(frozen=True, slots=True)
class ConsentGrant:
    purpose: str
    document_version: str


@dataclass(frozen=True, slots=True)
class MemberDraft:
    full_name: str
    email: str
    phone: str | None
    visitor_type: str | None
    visit_reason: str | None
    consents: tuple[ConsentGrant, ...]


@dataclass(frozen=True, slots=True)
class FormValues:
    full_name: str
    email: str
    phone: str | None
    visitor_type: str | None
    visit_reason: str | None


class TranscriptItem(BaseModel):
    """Item da transcrição. Não há campo de senha. Seção 8.1."""

    model_config = ConfigDict(extra="ignore")

    role: Literal["user", "assistant"]
    text: str
    created_at: datetime


def new_machine() -> Machine:
    return Machine(
        status=Status.COLLECTING_REQUIRED,
        fields=FieldSet(),
        password_set=False,
        correcting=False,
        field_errors=(),
        next_step=Step.FULL_NAME,
    )


def registration_deadline(now: datetime) -> datetime:
    return now + REGISTRATION_TTL


def session_is_expired(*, status: str, expires_at: datetime, now: datetime) -> bool:
    if status == Status.COMPLETED.value:
        return False
    return expires_at <= now


def accepts_message(machine: Machine) -> bool:
    return machine.status in _COLLECTING


def registration_rate_decision(
    *,
    count: int,
    now: datetime,
    window_start: datetime,
) -> RateDecision:
    if count <= REGISTRATION_IP_LIMIT:
        return RateDecision(limited=False, retry_after_seconds=0)
    return RateDecision(
        limited=True,
        retry_after_seconds=retry_after_seconds(now, window_start, REGISTRATION_WINDOW),
    )


def registration_window_start(now: datetime) -> datetime:
    return fixed_window_start(now, REGISTRATION_WINDOW)


def decide_next(machine: Machine) -> Machine:
    """Escolhe o próximo passo a partir dos campos, não da resposta do modelo."""
    if machine.status in (Status.COMPLETED, Status.ABANDONED):
        return machine
    if machine.correcting:
        return replace(
            machine,
            status=Status.COLLECTING_REQUIRED,
            next_step=Step.FULL_NAME,
        )
    missing_required = _first_required(machine.fields)
    if missing_required is not None:
        return replace(
            machine,
            status=Status.COLLECTING_REQUIRED,
            next_step=missing_required,
        )
    missing_optional = _first_optional(machine.fields)
    if missing_optional is not None:
        return replace(
            machine,
            status=Status.COLLECTING_OPTIONAL,
            next_step=missing_optional,
        )
    if not machine.password_set:
        return replace(
            machine,
            status=Status.AWAITING_PASSWORD,
            next_step=Step.PASSWORD,
        )
    if machine.status == Status.AWAITING_ACCEPTANCE:
        return replace(machine, next_step=Step.ACCEPTANCE)
    return replace(machine, status=Status.AWAITING_REVIEW, next_step=Step.REVIEW)


def apply_collected(machine: Machine, read: ToolRead) -> Machine:
    if read.rejected:
        return replace(machine, field_errors=())
    fields = machine.fields
    issues = list(read.issues)
    for name, value in read.values.items():
        fields = _assign(fields, name, value)
    progressed = bool(read.values)
    current = machine.next_step.value
    if read.skip_current and current not in read.values:
        if current in OPTIONAL_FIELDS:
            fields = _skip(fields, current)
            progressed = True
        else:
            issues.append(FieldIssue(current, "required"))
    correcting = machine.correcting and not progressed
    return replace(machine, fields=fields, field_errors=tuple(issues), correcting=correcting)


def apply_edits(machine: Machine, edits: Mapping[str, str | None]) -> Machine:
    fields = machine.fields
    issues: list[FieldIssue] = []
    changed = False
    for name, raw in edits.items():
        if name not in EDITABLE_FIELDS:
            continue
        if raw is None or not raw.strip():
            fields = _clear(fields, name)
            changed = True
            continue
        value, issue = validate_field(name, raw)
        if issue is not None:
            issues.append(issue)
            continue
        if value is None:
            continue
        fields = _assign(fields, name, value)
        changed = True
    status = machine.status
    correcting = False if changed else machine.correcting
    if changed and status in _REVIEWABLE:
        status = Status.COLLECTING_REQUIRED
    return decide_next(
        replace(
            machine,
            fields=fields,
            field_errors=tuple(issues),
            status=status,
            correcting=correcting,
        )
    )


def with_issue(machine: Machine, issue: FieldIssue) -> Machine:
    return replace(machine, field_errors=(*machine.field_errors, issue))


def mark_password_set(machine: Machine) -> Machine | None:
    if machine.status != Status.AWAITING_PASSWORD:
        return None
    return decide_next(replace(machine, password_set=True, field_errors=()))


def accept_review(machine: Machine) -> Machine | None:
    if machine.status != Status.AWAITING_REVIEW:
        return None
    return replace(
        machine,
        status=Status.AWAITING_ACCEPTANCE,
        next_step=Step.ACCEPTANCE,
        correcting=False,
        field_errors=(),
    )


def reject_review(machine: Machine) -> Machine | None:
    """Volta para a coleta para o visitante corrigir o resumo."""
    if machine.status != Status.AWAITING_REVIEW:
        return None
    return replace(
        machine,
        status=Status.COLLECTING_REQUIRED,
        next_step=Step.FULL_NAME,
        correcting=True,
        field_errors=(),
    )


def collect_form(values: FormValues) -> tuple[FieldSet, tuple[FieldIssue, ...]]:
    issues: list[FieldIssue] = []
    full_name, issue = _require("full_name", values.full_name)
    if issue is not None:
        issues.append(issue)
    email, issue = _require("email", values.email)
    if issue is not None:
        issues.append(issue)
    phone, phone_skipped, issue = _optional("phone", values.phone)
    if issue is not None:
        issues.append(issue)
    visitor_type, visitor_skipped, issue = _optional("visitor_type", values.visitor_type)
    if issue is not None:
        issues.append(issue)
    visit_reason, reason_skipped, issue = _optional("visit_reason", values.visit_reason)
    if issue is not None:
        issues.append(issue)
    return (
        FieldSet(
            full_name=full_name,
            email=email,
            phone=phone,
            phone_skipped=phone_skipped,
            visitor_type=visitor_type,
            visitor_type_skipped=visitor_skipped,
            visit_reason=visit_reason,
            visit_reason_skipped=reason_skipped,
        ),
        tuple(issues),
    )


def draft_member(
    fields: FieldSet,
    acceptance: Acceptance,
    *,
    expected_version: str,
    password_ready: bool,
) -> MemberDraft | tuple[FieldIssue, ...]:
    """Exige Termos, maioridade e senha. Sem personalização, descarta os campos sensíveis."""
    issues: list[FieldIssue] = []
    full_name = fields.full_name
    email = fields.email
    if full_name is None or not name_is_valid(full_name):
        issues.append(FieldIssue("full_name", "required" if full_name is None else "invalid"))
    if email is None or not email_is_valid(email):
        issues.append(FieldIssue("email", "required" if email is None else "invalid"))
    phone = fields.phone
    if phone is not None and not phone_is_valid(phone):
        issues.append(FieldIssue("phone", "invalid"))
        phone = None
    visitor_type = fields.visitor_type
    visit_reason = fields.visit_reason
    if visitor_type is not None and visitor_type not in VISITOR_TYPES:
        issues.append(FieldIssue("visitor_type", "invalid"))
    if visit_reason is not None and visit_reason not in VISIT_REASONS:
        issues.append(FieldIssue("visit_reason", "invalid"))
    if not password_ready:
        issues.append(FieldIssue("password", "required"))
    if not acceptance.accept_terms or acceptance.document_version != expected_version:
        issues.append(FieldIssue("accept_terms", "required"))
    if not acceptance.age_18_plus:
        issues.append(FieldIssue("age_18_plus", "required"))
    if issues or full_name is None or email is None:
        return tuple(issues)
    personalize = acceptance.profile_personalization
    consents = [
        ConsentGrant(Purpose.TERMS.value, expected_version),
        ConsentGrant(Purpose.AGE.value, expected_version),
    ]
    if personalize:
        consents.append(ConsentGrant(Purpose.PERSONALIZATION.value, expected_version))
    else:
        visitor_type = None
        visit_reason = None
    if acceptance.quality_improvement:
        consents.append(ConsentGrant(Purpose.QUALITY.value, expected_version))
    return MemberDraft(
        full_name=full_name,
        email=email,
        phone=phone,
        visitor_type=visitor_type if personalize else None,
        visit_reason=visit_reason if personalize else None,
        consents=tuple(consents),
    )


def public_fields(fields: FieldSet) -> PublicFields:
    return PublicFields(
        full_name=fields.full_name,
        email=fields.email,
        phone=fields.phone,
        visitor_type=fields.visitor_type,
        visit_reason=fields.visit_reason,
    )


def fields_document(machine: Machine) -> dict[str, object]:
    fields = machine.fields
    return {
        "full_name": fields.full_name,
        "email": fields.email,
        "phone": fields.phone,
        "phone_skipped": fields.phone_skipped,
        "visitor_type": fields.visitor_type,
        "visitor_type_skipped": fields.visitor_type_skipped,
        "visit_reason": fields.visit_reason,
        "visit_reason_skipped": fields.visit_reason_skipped,
        "correcting": machine.correcting,
        "next_step": machine.next_step.value,
        "errors": [{"field": issue.field, "code": issue.code} for issue in machine.field_errors],
    }


def machine_from_document(status: str, document: object, *, password_set: bool) -> Machine:
    data = document if isinstance(document, dict) else {}
    return Machine(
        status=_status(status),
        fields=FieldSet(
            full_name=_optional_str(data.get("full_name")),
            email=_optional_str(data.get("email")),
            phone=_optional_str(data.get("phone")),
            phone_skipped=data.get("phone_skipped") is True,
            visitor_type=_optional_str(data.get("visitor_type")),
            visitor_type_skipped=data.get("visitor_type_skipped") is True,
            visit_reason=_optional_str(data.get("visit_reason")),
            visit_reason_skipped=data.get("visit_reason_skipped") is True,
        ),
        password_set=password_set,
        correcting=data.get("correcting") is True,
        field_errors=_issues(data.get("errors")),
        next_step=_step(data.get("next_step")),
    )


def completed_document(draft: MemberDraft) -> dict[str, object]:
    machine = Machine(
        status=Status.COMPLETED,
        fields=FieldSet(
            full_name=draft.full_name,
            email=draft.email,
            phone=draft.phone,
            phone_skipped=draft.phone is None,
            visitor_type=draft.visitor_type,
            visitor_type_skipped=draft.visitor_type is None,
            visit_reason=draft.visit_reason,
            visit_reason_skipped=draft.visit_reason is None,
        ),
        password_set=False,
        correcting=False,
        field_errors=(),
        next_step=Step.ACCEPTANCE,
    )
    return fields_document(machine)


def dump_transcript(items: Sequence[TranscriptItem]) -> list[dict[str, object]]:
    return [dict(item.model_dump(mode="json")) for item in items]


def load_transcript(value: object) -> tuple[TranscriptItem, ...]:
    if not isinstance(value, list):
        return ()
    items: list[TranscriptItem] = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        try:
            items.append(TranscriptItem.model_validate(raw))
        except ValidationError:
            continue
    return tuple(items)


def _assign(fields: FieldSet, name: str, value: str) -> FieldSet:
    if name == "full_name":
        return replace(fields, full_name=value)
    if name == "email":
        return replace(fields, email=value)
    if name == "phone":
        return replace(fields, phone=value, phone_skipped=False)
    if name == "visitor_type":
        return replace(fields, visitor_type=value, visitor_type_skipped=False)
    if name == "visit_reason":
        return replace(fields, visit_reason=value, visit_reason_skipped=False)
    return fields


def _skip(fields: FieldSet, name: str) -> FieldSet:
    if name == "phone":
        return replace(fields, phone=None, phone_skipped=True)
    if name == "visitor_type":
        return replace(fields, visitor_type=None, visitor_type_skipped=True)
    if name == "visit_reason":
        return replace(fields, visit_reason=None, visit_reason_skipped=True)
    return fields


def _clear(fields: FieldSet, name: str) -> FieldSet:
    if name == "full_name":
        return replace(fields, full_name=None)
    if name == "email":
        return replace(fields, email=None)
    if name == "phone":
        return replace(fields, phone=None, phone_skipped=False)
    if name == "visitor_type":
        return replace(fields, visitor_type=None, visitor_type_skipped=False)
    if name == "visit_reason":
        return replace(fields, visit_reason=None, visit_reason_skipped=False)
    return fields


def _first_required(fields: FieldSet) -> Step | None:
    if fields.full_name is None:
        return Step.FULL_NAME
    if fields.email is None:
        return Step.EMAIL
    return None


def _first_optional(fields: FieldSet) -> Step | None:
    if fields.phone is None and not fields.phone_skipped:
        return Step.PHONE
    if fields.visitor_type is None and not fields.visitor_type_skipped:
        return Step.VISITOR_TYPE
    if fields.visit_reason is None and not fields.visit_reason_skipped:
        return Step.VISIT_REASON
    return None


def _require(name: str, raw: str) -> tuple[str | None, FieldIssue | None]:
    value, issue = validate_field(name, raw)
    if issue is not None:
        return None, issue
    if value is None:
        return None, FieldIssue(name, "required")
    return value, None


def _optional(name: str, raw: str | None) -> tuple[str | None, bool, FieldIssue | None]:
    if raw is None or not raw.strip():
        return None, True, None
    value, issue = validate_field(name, raw)
    if issue is not None:
        return None, False, issue
    return value, False, None


def _optional_str(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _issues(value: object) -> tuple[FieldIssue, ...]:
    if not isinstance(value, list):
        return ()
    issues: list[FieldIssue] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        field = item.get("field")
        code = item.get("code")
        if isinstance(field, str) and isinstance(code, str):
            issues.append(FieldIssue(field, code))
    return tuple(issues)


def _status(value: str) -> Status:
    try:
        return Status(value)
    except ValueError:
        return Status.COLLECTING_REQUIRED


def _step(value: object) -> Step:
    if isinstance(value, str):
        try:
            return Step(value)
        except ValueError:
            return Step.FULL_NAME
    return Step.FULL_NAME
