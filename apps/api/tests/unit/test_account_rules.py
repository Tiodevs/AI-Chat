"""As regras puras da conta do membro: correção do perfil, consentimentos e exclusão. FR-9.

Seções 8.5, 10.5, 11.5 e 12 do SDD (`PATCH /v1/me`, `PUT /v1/me/consents/{purpose}` e
`DELETE /v1/me`). Testa `app/domain/account.py` sem banco nem rede: só os campos enviados
mudam, os campos que podem indicar saúde exigem a personalização, os Termos só aceitam `true`,
a maioridade não muda e um admin não exclui a própria conta. As rotas com o banco ficam em
`tests/integration/test_account.py`.
"""

from app.domain.account import (
    delete_is_allowed,
    plan_profile_update,
    purpose_can_change,
)
from app.domain.fields import FieldIssue
from app.domain.registration import Purpose


def test_only_the_sent_fields_are_planned() -> None:
    plan = plan_profile_update({"full_name": "  Ana Souza  "}, personalization_active=False)
    assert plan.values == {"full_name": "Ana Souza"}
    assert plan.issues == ()


def test_optional_fields_can_be_cleared_but_the_name_cannot() -> None:
    plan = plan_profile_update({"phone": None, "full_name": ""}, personalization_active=False)
    assert plan.values == {"phone": None}
    assert plan.issues == (FieldIssue("full_name", "invalid"),)


def test_sensitive_fields_need_personalization() -> None:
    blocked = plan_profile_update(
        {"visitor_type": "patient", "visit_reason": "own_appointment"},
        personalization_active=False,
    )
    assert blocked.values == {}
    assert {issue.code for issue in blocked.issues} == {"personalization_required"}
    allowed = plan_profile_update(
        {"visitor_type": "patient", "visit_reason": "own_appointment"},
        personalization_active=True,
    )
    assert allowed.values == {"visitor_type": "patient", "visit_reason": "own_appointment"}


def test_clearing_a_sensitive_field_does_not_need_personalization() -> None:
    plan = plan_profile_update({"visitor_type": None}, personalization_active=False)
    assert plan.values == {"visitor_type": None}


def test_values_follow_the_field_rules_of_section_8_5() -> None:
    plan = plan_profile_update(
        {"full_name": "A", "phone": "abc", "visit_reason": "free text"},
        personalization_active=True,
    )
    assert plan.values == {}
    assert {issue.field for issue in plan.issues} == {"full_name", "phone", "visit_reason"}


def test_email_and_unknown_fields_are_not_editable() -> None:
    plan = plan_profile_update(
        {"email": "novo@example.com", "role": "admin"}, personalization_active=True
    )
    assert plan.values == {}
    assert {issue.field for issue in plan.issues} == {"email", "role"}


def test_terms_can_only_be_accepted_and_age_never_changes() -> None:
    assert purpose_can_change(Purpose.TERMS.value, granted=True)
    assert not purpose_can_change(Purpose.TERMS.value, granted=False)
    assert not purpose_can_change(Purpose.AGE.value, granted=True)
    assert not purpose_can_change(Purpose.AGE.value, granted=False)
    for purpose in (Purpose.PERSONALIZATION.value, Purpose.QUALITY.value):
        assert purpose_can_change(purpose, granted=True)
        assert purpose_can_change(purpose, granted=False)
    assert not purpose_can_change("anything_else", granted=True)


def test_an_admin_cannot_delete_the_own_account() -> None:
    assert not delete_is_allowed("admin")
    assert delete_is_allowed("member")
