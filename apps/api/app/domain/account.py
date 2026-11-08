"""Regras da conta do membro: correção do perfil, consentimentos e exclusão.

Camada de domínio (seção 6.2 do SDD). `AccountService` (`app/services/account.py`) chama estas
funções nos casos de uso de `PATCH /v1/me`, `PUT /v1/me/consents/{purpose}` e `DELETE /v1/me`,
e grava as ações de auditoria daqui. Usa as regras de campo de `fields.py` e as finalidades de
consentimento de `registration.py`. Seções 8.5, 10.5, 11.5, 11.6 e 12 do SDD.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from app.domain.fields import FieldIssue, validate_field
from app.domain.registration import Purpose

# Campos que `PATCH /v1/me` aceita. O e-mail fica de fora: ele é o acesso da conta (seção 12).
PROFILE_FIELDS = frozenset({"full_name", "phone", "visitor_type", "visit_reason"})
# Campos que podem indicar que a pessoa é paciente. Só mudam com a personalização ativa, e
# revogar a personalização os apaga (seções 11.4 e 12).
PERSONALIZED_FIELDS = ("visitor_type", "visit_reason")
# Opcionais que `null` ou texto vazio limpam. O nome é obrigatório e não pode ser limpo.
CLEARABLE_FIELDS = frozenset({"phone", "visitor_type", "visit_reason"})
# Finalidades que o membro liga e desliga na conta (seção 11.5).
REVOCABLE_PURPOSES = frozenset({Purpose.PERSONALIZATION.value, Purpose.QUALITY.value})
# Finalidades que a conta pode gravar. Nenhum código da API lê esta constante hoje: a regra
# vive em `purpose_can_change`.
SETTABLE_PURPOSES = REVOCABLE_PURPOSES | {Purpose.TERMS.value}
# Ações do log de auditoria (`audit_events`, seção 8.1).
ACCOUNT_DELETE_ACTION = "account.delete"
CONSENT_CHANGE_ACTION = "consent.change"
# Palavra que a tela pede antes de excluir a conta (seção 15.5). A API não confere esta palavra:
# a confirmação acontece só na interface, que tem a própria cópia em `apps/web/src/i18n/pt.ts`.
DELETE_CONFIRMATION = "EXCLUIR"


@dataclass(frozen=True, slots=True)
class ProfilePlan:
    """Valores já validados para gravar. `None` limpa o campo opcional.

    `issues` lista os erros por campo. Com algum erro, o serviço não grava nada e responde 422
    com uma mensagem por campo em `field_errors`.
    """

    values: dict[str, str | None]
    issues: tuple[FieldIssue, ...]


def plan_profile_update(
    changes: Mapping[str, str | None],
    *,
    personalization_active: bool,
) -> ProfilePlan:
    """Valida só os campos enviados. Os sensíveis exigem a personalização ativa.

    Para cada campo de `changes`, nesta ordem:

    1. Campo fora de `PROFILE_FIELDS`, inclusive `email`, vira erro `invalid`.
    2. `None` ou texto vazio limpa um opcional. No nome, vira erro `invalid`.
    3. `visitor_type` e `visit_reason` exigem `personalization_active`. Sem ela, o erro é
       `personalization_required`. Limpar continua permitido, porque o passo 2 vem antes.
    4. O valor passa por `validate_field`, com as regras da seção 8.5.

    Devolve o `ProfilePlan`. A função não grava nada: quem grava é o serviço.
    """
    values: dict[str, str | None] = {}
    issues: list[FieldIssue] = []
    for name, raw in changes.items():
        # 1. Só os campos do perfil. O e-mail não muda por aqui.
        if name not in PROFILE_FIELDS:
            issues.append(FieldIssue(name, "invalid"))
            continue
        # 2. Vazio limpa um opcional e é erro no nome.
        text = None if raw is None else raw.strip()
        if text is None or text == "":
            if name in CLEARABLE_FIELDS:
                values[name] = None
            else:
                issues.append(FieldIssue(name, "invalid"))
            continue
        # 3. Tipo e motivo só com o consentimento de personalização (seção 11.4).
        if name in PERSONALIZED_FIELDS and not personalization_active:
            issues.append(FieldIssue(name, "personalization_required"))
            continue
        # 4. As mesmas regras do cadastro.
        parsed, issue = validate_field(name, text)
        if issue is not None or parsed is None:
            issues.append(issue or FieldIssue(name, "invalid"))
            continue
        values[name] = parsed
    return ProfilePlan(values=values, issues=tuple(issues))


def purpose_can_change(purpose: str, *, granted: bool) -> bool:
    """Termos só se aceitam, e a maioridade não muda pela conta.

    Regra de `PUT /v1/me/consents/{purpose}` (seção 12). `terms_and_privacy_notice` só aceita
    `granted=True`: é assim que o membro aceita a versão nova dos documentos (seção 11.11).
    `age_18_plus` e finalidades desconhecidas devolvem falso, e o serviço responde 422.
    Personalização e melhoria mudam nos dois sentidos.
    """
    if purpose == Purpose.TERMS.value:
        return granted
    return purpose in REVOCABLE_PURPOSES


def delete_is_allowed(role: str) -> bool:
    """Um admin não exclui a própria conta pela API. Seção 10.5.

    Com falso, o serviço responde 403 com `ADMIN_CANNOT_DELETE`. A remoção de um admin é feita
    pelo script `bootstrap_admin --remove`, que recusa remover o último.
    """
    return role != "admin"
