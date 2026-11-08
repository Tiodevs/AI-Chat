"""Máquina de estados do cadastro. O modelo não conclui a conta. Seção 7.2.

Camada de domínio. Uma máquina de estados tem um conjunto fechado de estados e de transições:
cada função daqui recebe um `Machine` e devolve outro, ou `None` quando a transição não vale
no estado atual. O Gemini só extrai campos e formula a próxima pergunta; ele não conclui a
conta, não define `role`, não registra consentimento e não vê a senha (seção 7.2 e ADR-003).

Quem usa: o `RegistrationWorkflow` (`app/workflows/registration.py`) chama `apply_collected` e
`decide_next` nos nós `extract` e `decide_next` do grafo. O `RegistrationService`
(`app/services/registration.py`) chama o resto: carrega o estado do PostgreSQL com
`machine_from_document`, aplica a transição e grava com `fields_document`. Ele também grava os
dois estados finais: `completed` na conclusão e `abandoned` quando a sessão de 24 horas vence.
O controlador, os modelos e a migração `0005_registration` usam os enums e as restrições.

Transições no código, além do diagrama da seção 7.2: uma edição no cartão de resumo
(`apply_edits`) tira a sessão de `awaiting_password`, `awaiting_review` ou
`awaiting_acceptance` e deixa `decide_next` recalcular o passo; o formulário conclui uma sessão
em qualquer estado ativo. Não há rota de cancelamento: `abandoned` vem só da expiração.
"""

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

# O cadastro público só cria membro. Admin nasce do script `bootstrap_admin` (seção 10.5).
MEMBER_ROLE = "member"
# Validade da sessão de cadastro (seção 10.3). A tabela não guarda a criação: o funil da visão
# geral calcula o começo como `expires_at` menos este prazo.
REGISTRATION_TTL = timedelta(hours=24)
# Mensagens, senha e formulário: 20 pedidos por hora por IP (seção 10.4).
REGISTRATION_IP_LIMIT = 20
REGISTRATION_WINDOW = timedelta(hours=1)
REGISTRATION_IP_PURPOSE = "registration_ip"
# Tamanho máximo de uma mensagem do chat de cadastro, conferido no schema do pedido.
MAX_MESSAGE_CHARS = 1000


class Status(StrEnum):
    """Estado da sessão, gravado em `registration_sessions.status` (seção 7.2)."""

    COLLECTING_REQUIRED = "collecting_required"
    COLLECTING_OPTIONAL = "collecting_optional"
    AWAITING_PASSWORD = "awaiting_password"
    AWAITING_REVIEW = "awaiting_review"
    AWAITING_ACCEPTANCE = "awaiting_acceptance"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class Step(StrEnum):
    """Próximo passo, devolvido como `next_step` à interface.

    Os cinco primeiros pedem um campo. `password` troca o compositor pelo cartão de senha,
    porque a senha não é mensagem de chat. `review` e `acceptance` são os passos finais.
    """

    FULL_NAME = "full_name"
    EMAIL = "email"
    PHONE = "phone"
    VISITOR_TYPE = "visitor_type"
    VISIT_REASON = "visit_reason"
    PASSWORD = "password"
    REVIEW = "review"
    ACCEPTANCE = "acceptance"


class Path(StrEnum):
    """Caminho do cadastro: conversa ou formulário. Vai para as métricas e para o funil."""

    CHAT = "chat"
    FORM = "form"


class Purpose(StrEnum):
    """Finalidades de consentimento, em `consent_records.purpose` (seção 8.1).

    Termos e maioridade são obrigatórios; personalização e melhoria são opcionais (tabela do
    aceite da seção 7.2).
    """

    TERMS = "terms_and_privacy_notice"
    AGE = "age_18_plus"
    PERSONALIZATION = "profile_personalization"
    QUALITY = "quality_improvement"


class ConsentSource(StrEnum):
    """Onde o consentimento foi dado: no aceite do chat, no formulário ou na conta."""

    CHAT = "chat"
    FORM = "form"
    ACCOUNT = "account"


# Restrições CHECK geradas dos enums. Os modelos e a migração `0005_registration` importam estas
# expressões; um valor novo pede uma migração que troque a restrição.
STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{item.value}'" for item in Status) + ")"
PATH_CHECK_SQL = "path IN (" + ", ".join(f"'{item.value}'" for item in Path) + ")"
PURPOSE_CHECK_SQL = "purpose IN (" + ", ".join(f"'{item.value}'" for item in Purpose) + ")"
SOURCE_CHECK_SQL = "source IN (" + ", ".join(f"'{item.value}'" for item in ConsentSource) + ")"

# Estados em que o chat aceita mensagem.
_COLLECTING = frozenset({Status.COLLECTING_REQUIRED, Status.COLLECTING_OPTIONAL})
# Estados depois da coleta. Uma edição que muda um campo volta deles para a coleta.
_REVIEWABLE = frozenset(
    {Status.AWAITING_REVIEW, Status.AWAITING_ACCEPTANCE, Status.AWAITING_PASSWORD}
)


@dataclass(frozen=True, slots=True)
class FieldSet:
    """Campos entendidos até agora.

    Um opcional tem três situações: com valor, pulado (`*_skipped`) ou ainda não perguntado.
    Só a terceira faz `decide_next` pedir o campo.
    """

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
    """Estado completo do cadastro num momento.

    É imutável: cada transição devolve uma cópia nova com `dataclasses.replace`.

    - `password_set` vem da presença de `password_hash` no banco; a senha nunca entra aqui.
    - `correcting` marca o modo de correção, depois de Quero corrigir na revisão.
    - `field_errors` são os erros do último turno ou da última edição.
    - `next_step` é o passo que a resposta devolve como `next_step`.
    """

    status: Status
    fields: FieldSet
    password_set: bool
    correcting: bool
    field_errors: tuple[FieldIssue, ...]
    next_step: Step


@dataclass(frozen=True, slots=True)
class PublicFields:
    """Os campos como a API devolve em `fields`, sem as marcas de pulado."""

    full_name: str | None
    email: str | None
    phone: str | None
    visitor_type: str | None
    visit_reason: str | None


@dataclass(frozen=True, slots=True)
class Acceptance:
    """Os aceites do pedido de conclusão, da tabela do aceite da seção 7.2.

    `document_version` precisa ser a `LEGAL_DOCUMENT_VERSION` vigente.
    """

    accept_terms: bool
    document_version: str
    age_18_plus: bool
    profile_personalization: bool
    quality_improvement: bool


@dataclass(frozen=True, slots=True)
class ConsentGrant:
    """Um consentimento a gravar em `consent_records`, com a versão do documento."""

    purpose: str
    document_version: str


@dataclass(frozen=True, slots=True)
class MemberDraft:
    """O membro pronto para inserir.

    Campos validados, sensíveis já descartados sem personalização, e os consentimentos.
    """

    full_name: str
    email: str
    phone: str | None
    visitor_type: str | None
    visit_reason: str | None
    consents: tuple[ConsentGrant, ...]


@dataclass(frozen=True, slots=True)
class FormValues:
    """Os campos do formulário como chegaram, antes da validação."""

    full_name: str
    email: str
    phone: str | None
    visitor_type: str | None
    visit_reason: str | None


class TranscriptItem(BaseModel):
    """Item da transcrição. Não há campo de senha. Seção 8.1.

    É um modelo Pydantic porque a transcrição é JSON no banco. `extra="ignore"` descarta
    qualquer chave a mais ao ler o JSON gravado, então ela não volta na resposta.
    """

    model_config = ConfigDict(extra="ignore")

    role: Literal["user", "assistant"]
    text: str
    created_at: datetime


def new_machine() -> Machine:
    """Estado inicial: coleta dos obrigatórios, pedindo o nome."""
    return Machine(
        status=Status.COLLECTING_REQUIRED,
        fields=FieldSet(),
        password_set=False,
        correcting=False,
        field_errors=(),
        next_step=Step.FULL_NAME,
    )


def registration_deadline(now: datetime) -> datetime:
    """Fim da validade da sessão: 24 horas depois de `now`."""
    return now + REGISTRATION_TTL


def session_is_expired(*, status: str, expires_at: datetime, now: datetime) -> bool:
    """A sessão venceu quando `expires_at` passou. Uma sessão concluída nunca vence aqui.

    Assim um aceite repetido continua devolvendo o mesmo usuário (seção 7.2), até a retenção
    apagar a linha depois de `expires_at` (seção 11.6).
    """
    if status == Status.COMPLETED.value:
        return False
    return expires_at <= now


def accepts_message(machine: Machine) -> bool:
    """O chat só aceita mensagem na coleta. Fora dela, o serviço responde `WRONG_STEP`."""
    return machine.status in _COLLECTING


def registration_rate_decision(
    *,
    count: int,
    now: datetime,
    window_start: datetime,
) -> RateDecision:
    """Decide o 429 do 21º pedido do IP na hora. A contagem inclui o pedido atual."""
    if count <= REGISTRATION_IP_LIMIT:
        return RateDecision(limited=False, retry_after_seconds=0)
    return RateDecision(
        limited=True,
        retry_after_seconds=retry_after_seconds(now, window_start, REGISTRATION_WINDOW),
    )


def registration_window_start(now: datetime) -> datetime:
    """Começo da janela de uma hora do balde por IP."""
    return fixed_window_start(now, REGISTRATION_WINDOW)


def decide_next(machine: Machine) -> Machine:
    """Escolhe o próximo passo a partir dos campos, não da resposta do modelo.

    Nesta ordem:

    1. `completed` e `abandoned` não mudam.
    2. No modo de correção, volta à coleta dos obrigatórios. O passo fica em `full_name`, mas
       a frase é a pergunta de correção (`prompt_for` com `correcting`).
    3. Falta obrigatório: pede o primeiro, o nome e depois o e-mail.
    4. Falta opcional nem respondido nem pulado: pede o primeiro, na ordem telefone, tipo de
       visitante e motivo.
    5. Sem senha: `awaiting_password`.
    6. Em `awaiting_acceptance`, continua no aceite.
    7. Senão, revisão. Com a senha já gravada, a coleta vai direto para a revisão.
    """
    # 1.
    if machine.status in (Status.COMPLETED, Status.ABANDONED):
        return machine
    # 2.
    if machine.correcting:
        return replace(
            machine,
            status=Status.COLLECTING_REQUIRED,
            next_step=Step.FULL_NAME,
        )
    # 3.
    missing_required = _first_required(machine.fields)
    if missing_required is not None:
        return replace(
            machine,
            status=Status.COLLECTING_REQUIRED,
            next_step=missing_required,
        )
    # 4.
    missing_optional = _first_optional(machine.fields)
    if missing_optional is not None:
        return replace(
            machine,
            status=Status.COLLECTING_OPTIONAL,
            next_step=missing_optional,
        )
    # 5.
    if not machine.password_set:
        return replace(
            machine,
            status=Status.AWAITING_PASSWORD,
            next_step=Step.PASSWORD,
        )
    # 6.
    if machine.status == Status.AWAITING_ACCEPTANCE:
        return replace(machine, next_step=Step.ACCEPTANCE)
    # 7.
    return replace(machine, status=Status.AWAITING_REVIEW, next_step=Step.REVIEW)


def apply_collected(machine: Machine, read: ToolRead) -> Machine:
    """Aplica a leitura da ferramenta ao estado. Nó `extract` do grafo, seção 7.2.

    1. Uma saída rejeitada não aplica nada e limpa os erros do turno anterior.
    2. Cada valor aceito substitui o campo, mesmo que ele já tivesse valor: a pessoa corrige
       um dado dizendo o novo valor.
    3. `skip_current` pula o passo atual quando ele é opcional e o turno não trouxe valor para
       ele. Num obrigatório, vira o erro `required`.
    4. O modo de correção termina quando o turno trouxe algum campo ou pulou um opcional.

    Não escolhe o passo: `decide_next` roda depois, no grafo.
    """
    # 1.
    if read.rejected:
        return replace(machine, field_errors=())
    # 2.
    fields = machine.fields
    issues = list(read.issues)
    for name, value in read.values.items():
        fields = _assign(fields, name, value)
    progressed = bool(read.values)
    # 3.
    current = machine.next_step.value
    if read.skip_current and current not in read.values:
        if current in OPTIONAL_FIELDS:
            fields = _skip(fields, current)
            progressed = True
        else:
            issues.append(FieldIssue(current, "required"))
    # 4.
    correcting = machine.correcting and not progressed
    return replace(machine, fields=fields, field_errors=tuple(issues), correcting=correcting)


def apply_edits(machine: Machine, edits: Mapping[str, str | None]) -> Machine:
    """Aplica as edições do cartão de resumo e recalcula o passo.

    Regra de `PATCH /v1/registration/sessions/{id}/fields` (seção 12), com as regras do
    formulário:

    1. Campos fora de `EDITABLE_FIELDS` são ignorados.
    2. Valor vazio ou `None` limpa o campo. Um opcional limpo volta a ser perguntado.
    3. Os outros valores passam por `validate_field`; um inválido vira erro e não muda o
       campo.
    4. Com alguma mudança, sai do modo de correção e, se a coleta já tinha terminado, volta
       para `collecting_required`. Um nome editado no aceite passa de novo pela revisão.
    5. `decide_next` escolhe o passo.

    O e-mail que já tem conta é conferido antes, pelo serviço, que tira o e-mail das edições e
    acrescenta o erro com `with_issue`.
    """
    fields = machine.fields
    issues: list[FieldIssue] = []
    changed = False
    for name, raw in edits.items():
        # 1.
        if name not in EDITABLE_FIELDS:
            continue
        # 2.
        if raw is None or not raw.strip():
            fields = _clear(fields, name)
            changed = True
            continue
        # 3.
        value, issue = validate_field(name, raw)
        if issue is not None:
            issues.append(issue)
            continue
        if value is None:
            continue
        fields = _assign(fields, name, value)
        changed = True
    # 4.
    status = machine.status
    correcting = False if changed else machine.correcting
    if changed and status in _REVIEWABLE:
        status = Status.COLLECTING_REQUIRED
    # 5.
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
    """Acrescenta um erro de campo. O serviço usa para o e-mail que já tem conta no cartão."""
    return replace(machine, field_errors=(*machine.field_errors, issue))


def mark_password_set(machine: Machine) -> Machine | None:
    """Registra que o hash da senha foi gravado e avança para a revisão.

    Só vale em `awaiting_password`; fora dele, devolve `None`, e o serviço responde
    `WRONG_STEP`. A senha não passa por aqui: o serviço grava o hash e chama esta função.
    """
    if machine.status != Status.AWAITING_PASSWORD:
        return None
    return decide_next(replace(machine, password_set=True, field_errors=()))


def accept_review(machine: Machine) -> Machine | None:
    """A pessoa confirmou o resumo (Está certo): vai para o aceite.

    Só vale em `awaiting_review`; fora dele, devolve `None`.
    """
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
    """Volta para a coleta para o visitante corrigir o resumo.

    É o botão Quero corrigir: liga o modo de correção, e a próxima fala é "O que você quer
    corrigir no cadastro?". Só vale em `awaiting_review`; fora dele, devolve `None`.
    """
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
    """Valida os campos do formulário com as mesmas regras do chat (seção 7.2).

    Devolve os campos e todos os erros juntos, para a tela marcar cada campo de uma vez. Um
    opcional em branco conta como pulado.
    """
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
    """Exige Termos, maioridade e senha. Sem personalização, descarta os campos sensíveis.

    Passos 1 e 2 da conclusão da seção 7.2. O aceite do chat e o formulário chamam esta mesma
    função.

    1. Exige nome e e-mail válidos, um hash de senha (`password_ready`), o aceite dos Termos na
       versão vigente e a declaração de maioridade. Confere de novo telefone, tipo e motivo.
    2. Com algum problema, devolve a tupla de erros e não monta o membro.
    3. Inclui sempre os consentimentos de Termos e de maioridade, com `expected_version`.
    4. Sem o consentimento de personalização, descarta `visitor_type` e `visit_reason`.
    5. Inclui a melhoria só se ela foi aceita.
    """
    # 1.
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
    # 2. Os testes de `None` também estreitam o tipo para o mypy.
    if issues or full_name is None or email is None:
        return tuple(issues)
    # 3.
    personalize = acceptance.profile_personalization
    consents = [
        ConsentGrant(Purpose.TERMS.value, expected_version),
        ConsentGrant(Purpose.AGE.value, expected_version),
    ]
    # 4.
    if personalize:
        consents.append(ConsentGrant(Purpose.PERSONALIZATION.value, expected_version))
    else:
        visitor_type = None
        visit_reason = None
    # 5.
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
    """Os campos sem as marcas de pulado, para a resposta da API e para `review_prompt`."""
    return PublicFields(
        full_name=fields.full_name,
        email=fields.email,
        phone=fields.phone,
        visitor_type=fields.visitor_type,
        visit_reason=fields.visit_reason,
    )


def fields_document(machine: Machine) -> dict[str, object]:
    """JSON gravado em `registration_sessions.fields`.

    Além dos campos e das marcas de pulado, guarda `correcting`, `next_step` e os erros do
    último turno. O `status` fica na própria coluna, e `password_set` vem de `password_hash`.
    """
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
    """Reconstrói o `Machine` a partir das colunas da sessão.

    O JSON vem do banco e é lido com desconfiança: um valor de tipo errado vira `None` ou
    falso, e um status ou um passo desconhecido voltam ao começo da coleta.
    """
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
    """JSON de uma sessão concluída: os campos do membro criado, sem senha e sem erros.

    Os opcionais vazios ficam marcados como pulados, e `password_set` é falso porque o serviço
    apaga o hash da sessão na conclusão.
    """
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
    """Transcrição em JSON para `registration_sessions.transcript`, com as datas em ISO."""
    return [dict(item.model_dump(mode="json")) for item in items]


def load_transcript(value: object) -> tuple[TranscriptItem, ...]:
    """Lê a transcrição gravada, ignorando o item que não é objeto ou não é válido.

    Um item ruim some da leitura em vez de quebrar a sessão inteira.
    """
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
    """Grava um valor no campo. Num opcional, desfaz a marca de pulado."""
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
    """Marca um opcional como pulado, sem valor."""
    if name == "phone":
        return replace(fields, phone=None, phone_skipped=True)
    if name == "visitor_type":
        return replace(fields, visitor_type=None, visitor_type_skipped=True)
    if name == "visit_reason":
        return replace(fields, visit_reason=None, visit_reason_skipped=True)
    return fields


def _clear(fields: FieldSet, name: str) -> FieldSet:
    """Esvazia o campo e a marca de pulado: o campo volta a ser perguntado."""
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
    """Primeiro obrigatório sem valor, na ordem da seção 7.2."""
    if fields.full_name is None:
        return Step.FULL_NAME
    if fields.email is None:
        return Step.EMAIL
    return None


def _first_optional(fields: FieldSet) -> Step | None:
    """Primeiro opcional nem respondido nem pulado."""
    if fields.phone is None and not fields.phone_skipped:
        return Step.PHONE
    if fields.visitor_type is None and not fields.visitor_type_skipped:
        return Step.VISITOR_TYPE
    if fields.visit_reason is None and not fields.visit_reason_skipped:
        return Step.VISIT_REASON
    return None


def _require(name: str, raw: str) -> tuple[str | None, FieldIssue | None]:
    """Valida um obrigatório do formulário. Texto vazio vira `invalid`, pela regra de tamanho."""
    value, issue = validate_field(name, raw)
    if issue is not None:
        return None, issue
    if value is None:
        return None, FieldIssue(name, "required")
    return value, None


def _optional(name: str, raw: str | None) -> tuple[str | None, bool, FieldIssue | None]:
    """Valida um opcional do formulário. Em branco, conta como pulado."""
    if raw is None or not raw.strip():
        return None, True, None
    value, issue = validate_field(name, raw)
    if issue is not None:
        return None, False, issue
    return value, False, None


def _optional_str(value: object) -> str | None:
    """Texto não vazio do JSON, ou `None` para qualquer outro valor."""
    if isinstance(value, str) and value:
        return value
    return None


def _issues(value: object) -> tuple[FieldIssue, ...]:
    """Erros de campo gravados no JSON. Um item malformado é ignorado."""
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
    """Status gravado, ou `collecting_required` quando o valor é desconhecido."""
    try:
        return Status(value)
    except ValueError:
        return Status.COLLECTING_REQUIRED


def _step(value: object) -> Step:
    """Passo gravado, ou `full_name` quando o valor é desconhecido."""
    if isinstance(value, str):
        try:
            return Step(value)
        except ValueError:
            return Step.FULL_NAME
    return Step.FULL_NAME
