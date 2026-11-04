"""Regras da conta do membro: correção, consentimentos e exclusão. Seções 11.5, 11.6 e 12."""

from collections.abc import Mapping
from dataclasses import dataclass

from app.domain.fields import FieldIssue, validate_field
from app.domain.registration import Purpose

PROFILE_FIELDS = frozenset({"full_name", "phone", "visitor_type", "visit_reason"})
PERSONALIZED_FIELDS = ("visitor_type", "visit_reason")
CLEARABLE_FIELDS = frozenset({"phone", "visitor_type", "visit_reason"})
REVOCABLE_PURPOSES = frozenset({Purpose.PERSONALIZATION.value, Purpose.QUALITY.value})
SETTABLE_PURPOSES = REVOCABLE_PURPOSES | {Purpose.TERMS.value}
ACCOUNT_DELETE_ACTION = "account.delete"
CONSENT_CHANGE_ACTION = "consent.change"
DELETE_CONFIRMATION = "EXCLUIR"


@dataclass(frozen=True, slots=True)
class ProfilePlan:
    """Valores já validados para gravar. `None` limpa o campo opcional."""

    values: dict[str, str | None]
    issues: tuple[FieldIssue, ...]


def plan_profile_update(
    changes: Mapping[str, str | None],
    *,
    personalization_active: bool,
) -> ProfilePlan:
    """Valida só os campos enviados. Os sensíveis exigem a personalização ativa."""
    values: dict[str, str | None] = {}
    issues: list[FieldIssue] = []
    for name, raw in changes.items():
        if name not in PROFILE_FIELDS:
            issues.append(FieldIssue(name, "invalid"))
            continue
        text = None if raw is None else raw.strip()
        if text is None or text == "":
            if name in CLEARABLE_FIELDS:
                values[name] = None
            else:
                issues.append(FieldIssue(name, "invalid"))
            continue
        if name in PERSONALIZED_FIELDS and not personalization_active:
            issues.append(FieldIssue(name, "personalization_required"))
            continue
        parsed, issue = validate_field(name, text)
        if issue is not None or parsed is None:
            issues.append(issue or FieldIssue(name, "invalid"))
            continue
        values[name] = parsed
    return ProfilePlan(values=values, issues=tuple(issues))


def purpose_can_change(purpose: str, *, granted: bool) -> bool:
    """Termos só se aceitam, e a maioridade não muda pela conta."""
    if purpose == Purpose.TERMS.value:
        return granted
    return purpose in REVOCABLE_PURPOSES


def delete_is_allowed(role: str) -> bool:
    """Um admin não exclui a própria conta pela API. Seção 10.5."""
    return role != "admin"
