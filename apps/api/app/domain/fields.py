"""Regras dos campos do cadastro. Seção 8.5 do SDD.

Camada de domínio. Também guarda a lista de permissão da ferramenta `set_fields`, que o modelo
usa no cadastro por chat (seção 10.2). Quem usa: `registration.py` e `account.py` deste
pacote, `RegistrationService`, o `RegistrationWorkflow` (`app/workflows/registration.py`), o
`DemoChatProvider`, o modelo `User` e a migração `0005_registration`. O chat, o cartão de
resumo, o formulário e a página da conta validam com o mesmo `validate_field`.
"""

from dataclasses import dataclass

from app.domain.auth import email_is_valid, normalize_email, password_length_is_valid

# Limites da seção 8.5, em caracteres.
FULL_NAME_MIN = 2
FULL_NAME_MAX = 80
PHONE_MIN = 7
PHONE_MAX = 20
# Listas fechadas, sem texto livre (seção 11.2, necessidade). Os dois campos podem indicar que
# a pessoa é paciente e só são gravados com o consentimento de personalização (seção 11.4).
VISITOR_TYPES = ("patient", "visitor", "caregiver")
VISIT_REASONS = (
    "visiting_someone",
    "own_appointment",
    "exam_or_test",
    "accompanying_someone",
    "administrative",
    "other",
)
# Ordem da coleta da seção 7.2. Nenhum código lê `REQUIRED_FIELDS` hoje: a ordem dos
# obrigatórios vale em `registration._first_required`, e a dos opcionais em
# `registration._first_optional`. `OPTIONAL_FIELDS` diz se o passo atual pode ser pulado.
REQUIRED_FIELDS = ("full_name", "email")
OPTIONAL_FIELDS = ("phone", "visitor_type", "visit_reason")
# Lista de permissão da ferramenta (seção 10.2). `role`, senha e consentimentos não estão aqui,
# então uma saída do modelo com qualquer um deles é rejeitada inteira.
TOOL_KEYS = frozenset(
    {"full_name", "email", "phone", "visitor_type", "visit_reason", "skip_current"}
)
# Campos que o cartão de resumo edita (`PATCH /v1/registration/sessions/{id}/fields`).
EDITABLE_FIELDS = frozenset({"full_name", "email", "phone", "visitor_type", "visit_reason"})
SET_FIELDS_TOOL_NAME = "set_fields"

# Restrição CHECK de `users.visit_reason`, gerada da lista acima. O modelo `User` e a migração
# `0005_registration` importam esta expressão. Um motivo novo não muda um banco já migrado: ele
# pede uma migração que troque a restrição.
VISIT_REASON_CHECK_SQL = (
    "visit_reason IS NULL OR visit_reason IN ("
    + ", ".join(f"'{item}'" for item in VISIT_REASONS)
    + ")"
)

# Caracteres aceitos no telefone: dígitos, espaço e `+ - ( )` (seção 8.5).
_PHONE_CHARS = frozenset("0123456789+-() ")


@dataclass(frozen=True, slots=True)
class FieldIssue:
    """Erro de um campo: o nome do campo e um código.

    Códigos usados: `invalid`, `required`, `taken` (e-mail que já tem conta) e
    `personalization_required` (conta sem personalização). A mensagem em português de cada par
    está em `message_for`, de `app/prompts/registration.py`.
    """

    field: str
    code: str


@dataclass(frozen=True, slots=True)
class ToolRead:
    """Saída aceita da ferramenta. Rejeitada, nenhum campo entra.

    `values` tem os valores já validados e normalizados. `issues` tem os campos que vieram com
    valor inválido. `skip_current` diz que a pessoa pulou o passo atual. Com `rejected`, o
    turno não aplica nada, e os outros campos vêm vazios.
    """

    rejected: bool
    values: dict[str, str]
    issues: tuple[FieldIssue, ...]
    skip_current: bool

    def without_email(self) -> "ToolRead":
        """Cópia sem o e-mail, com o erro `taken` no lugar.

        O workflow chama quando o e-mail extraído já tem conta. O e-mail já entendido não é
        sobrescrito (seção 7.2, passo 2), e o turno responde com a fala fixa de e-mail usado.
        """
        values = {key: value for key, value in self.values.items() if key != "email"}
        issues = tuple(issue for issue in self.issues if issue.field != "email")
        return ToolRead(
            rejected=False,
            values=values,
            issues=(*issues, FieldIssue("email", "taken")),
            skip_current=self.skip_current,
        )


def set_fields_parameters() -> dict[str, object]:
    """Schema da ferramenta. Só os campos da lista de permissão. Seção 10.2.

    É o JSON Schema dos argumentos de `set_fields`. `additionalProperties: false` pede ao
    modelo que não invente chave, e `read_tool_arguments` confere de novo, porque o modelo
    pode desobedecer. `visitor_type` e `visit_reason` são enums. O workflow acrescenta a
    descrição de cada campo, que mora em `app/prompts/registration.py`.
    """
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
    """Leitura que descarta a saída inteira.

    O workflow usa quando o modelo não chamou `set_fields`, por exemplo numa dúvida sem dado.
    """
    return ToolRead(rejected=True, values={}, issues=(), skip_current=False)


def read_tool_arguments(arguments: object) -> ToolRead:
    """Chave fora da lista rejeita a saída inteira, inclusive `role` e consentimentos.

    Valida os argumentos que o modelo mandou para `set_fields` (seção 10.2):

    1. Argumentos que não são um objeto rejeitam a saída.
    2. Uma chave fora de `TOOL_KEYS` rejeita a saída inteira: nenhum campo do turno entra.
    3. `null` é ignorado. `skip_current` precisa ser booleano, e os outros campos, texto; um
       tipo errado rejeita a saída.
    4. Cada valor passa por `validate_field`. Um valor inválido vira erro do campo, sem
       rejeitar os outros.
    """
    # 1.
    if not isinstance(arguments, dict):
        return rejected_tool()
    # 2.
    if any(key not in TOOL_KEYS for key in arguments):
        return rejected_tool()
    values: dict[str, str] = {}
    issues: list[FieldIssue] = []
    skip = False
    for key, raw in arguments.items():
        # 3.
        if raw is None:
            continue
        if key == "skip_current":
            if not isinstance(raw, bool):
                return rejected_tool()
            skip = raw
            continue
        if not isinstance(raw, str):
            return rejected_tool()
        # 4.
        parsed, issue = validate_field(str(key), raw)
        if issue is not None:
            issues.append(issue)
            continue
        if parsed is not None:
            values[str(key)] = parsed
    return ToolRead(rejected=False, values=values, issues=tuple(issues), skip_current=skip)


def validate_field(name: str, raw: str) -> tuple[str | None, FieldIssue | None]:
    """Valida e normaliza um campo pelas regras da seção 8.5.

    Devolve `(valor, None)` quando o valor serve, ou `(None, FieldIssue)` quando não serve;
    nunca os dois `None`. Nome, telefone e as listas perdem os espaços das pontas; o e-mail
    também vira minúsculo. Um nome de campo desconhecido vira `invalid`.
    """
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
    """Nome com 2 a 80 caracteres."""
    return FULL_NAME_MIN <= len(value) <= FULL_NAME_MAX


def phone_is_valid(value: str) -> bool:
    """Telefone com 7 a 20 caracteres, só dígitos, espaço e `+ - ( )`."""
    return PHONE_MIN <= len(value) <= PHONE_MAX and all(char in _PHONE_CHARS for char in value)


def password_is_acceptable(password: str) -> bool:
    """Senha do cadastro: de 12 a 72 caracteres.

    A senha nunca passa por `validate_field` nem pela ferramenta: ela tem rota própria e vai
    direto para o hash (seção 7.2).
    """
    return password_length_is_valid(password)
