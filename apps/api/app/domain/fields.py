"""Regras dos campos do cadastro. Seção 8.5 do SDD."""

from dataclasses import dataclass

from app.domain.auth import email_is_valid, normalize_email, password_length_is_valid

FULL_NAME_MIN = 2
FULL_NAME_MAX = 80
PHONE_MIN = 7
PHONE_MAX = 20
VISITOR_TYPES = ("patient", "visitor", "caregiver")
VISIT_REASONS = (
    "visiting_someone",
    "own_appointment",
    "exam_or_test",
    "accompanying_someone",
    "administrative",
    "other",
)
REQUIRED_FIELDS = ("full_name", "email")
OPTIONAL_FIELDS = ("phone", "visitor_type", "visit_reason")
TOOL_KEYS = frozenset(
    {"full_name", "email", "phone", "visitor_type", "visit_reason", "skip_current"}
)
EDITABLE_FIELDS = frozenset({"full_name", "email", "phone", "visitor_type", "visit_reason"})
SET_FIELDS_TOOL_NAME = "set_fields"

VISIT_REASON_CHECK_SQL = (
    "visit_reason IS NULL OR visit_reason IN ("
    + ", ".join(f"'{item}'" for item in VISIT_REASONS)
    + ")"
)

_PHONE_CHARS = frozenset("0123456789+-() ")


@dataclass(frozen=True, slots=True)
class FieldIssue:
    field: str
    code: str


@dataclass(frozen=True, slots=True)
class ToolRead:
    """Saída aceita da ferramenta. Rejeitada, nenhum campo entra."""

    rejected: bool
    values: dict[str, str]
    issues: tuple[FieldIssue, ...]
    skip_current: bool

    def without_email(self) -> "ToolRead":
        values = {key: value for key, value in self.values.items() if key != "email"}
        issues = tuple(issue for issue in self.issues if issue.field != "email")
        return ToolRead(
            rejected=False,
            values=values,
            issues=(*issues, FieldIssue("email", "taken")),
            skip_current=self.skip_current,
        )


def set_fields_parameters() -> dict[str, object]:
    """Schema da ferramenta. Só os campos da lista de permissão. Seção 10.2."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "full_name": {"type": "string"},
            "email": {"type": "string"},
            "phone": {"type": "string"},
            "visitor_type": {"type": "string", "enum": list(VISITOR_TYPES)},
            "visit_reason": {"type": "string", "enum": list(VISIT_REASONS)},
            "skip_current": {"type": "boolean"},
        },
    }


def rejected_tool() -> ToolRead:
    return ToolRead(rejected=True, values={}, issues=(), skip_current=False)


def read_tool_arguments(arguments: object) -> ToolRead:
    """Chave fora da lista rejeita a saída inteira, inclusive `role` e consentimentos."""
    if not isinstance(arguments, dict):
        return rejected_tool()
    if any(key not in TOOL_KEYS for key in arguments):
        return rejected_tool()
    values: dict[str, str] = {}
    issues: list[FieldIssue] = []
    skip = False
    for key, raw in arguments.items():
        if raw is None:
            continue
        if key == "skip_current":
            if not isinstance(raw, bool):
                return rejected_tool()
            skip = raw
            continue
        if not isinstance(raw, str):
            return rejected_tool()
        parsed, issue = validate_field(str(key), raw)
        if issue is not None:
            issues.append(issue)
            continue
        if parsed is not None:
            values[str(key)] = parsed
    return ToolRead(rejected=False, values=values, issues=tuple(issues), skip_current=skip)


def validate_field(name: str, raw: str) -> tuple[str | None, FieldIssue | None]:
    if name == "full_name":
        value = raw.strip()
        if not name_is_valid(value):
            return None, FieldIssue("full_name", "invalid")
        return value, None
    if name == "email":
        value = normalize_email(raw)
        if not email_is_valid(value):
            return None, FieldIssue("email", "invalid")
        return value, None
    if name == "phone":
        value = raw.strip()
        if not phone_is_valid(value):
            return None, FieldIssue("phone", "invalid")
        return value, None
    if name == "visitor_type":
        value = raw.strip()
        if value not in VISITOR_TYPES:
            return None, FieldIssue("visitor_type", "invalid")
        return value, None
    if name == "visit_reason":
        value = raw.strip()
        if value not in VISIT_REASONS:
            return None, FieldIssue("visit_reason", "invalid")
        return value, None
    return None, FieldIssue(name, "invalid")


def name_is_valid(value: str) -> bool:
    return FULL_NAME_MIN <= len(value) <= FULL_NAME_MAX


def phone_is_valid(value: str) -> bool:
    return PHONE_MIN <= len(value) <= PHONE_MAX and all(char in _PHONE_CHARS for char in value)


def password_is_acceptable(password: str) -> bool:
    return password_length_is_valid(password)
