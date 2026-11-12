"""Remoção automática de identificadores da mensagem do visitante. Seção 29.9.7 do SDD.

Camada de domínio, só a biblioteca padrão. `services/handoff.py` chama `redact_identifiers`
antes de gravar a mensagem do visitante e antes do `NOTIFY`; a mensagem da equipe não passa
por aqui, porque segue as normas da seção 29.3. Os telefones do catálogo da seção 9, nas
formas que `domain/phones.py` reconhece, ficam fora de todas as regras. FR-25.

As regras rodam na ordem da tabela da seção 29.9.7: e-mail, CPF, cartão, telefone e número
longo. Cada uma troca o trecho pelo marcador, e os marcadores não têm dígito, então uma regra
seguinte nunca casa dentro de um marcador. O visitante recebe de volta a mensagem como ela foi
gravada e vê o que saiu.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.phones import catalog_phone_spans


class IdentifierKind(StrEnum):
    """O tipo do identificador removido. Vai no rótulo `kind` de `atrium_handoff_redactions`."""

    EMAIL = "email"
    CPF = "cpf"
    CARD = "card"
    PHONE = "phone"
    NUMBER = "number"


# Os marcadores da seção 29.9.7, em português, como o visitante os vê.
MARKERS: dict[IdentifierKind, str] = {
    IdentifierKind.EMAIL: "[e-mail removido]",
    IdentifierKind.CPF: "[CPF removido]",
    IdentifierKind.CARD: "[cartão removido]",
    IdentifierKind.PHONE: "[telefone removido]",
    IdentifierKind.NUMBER: "[número removido]",
}

# 1. O mesmo padrão de e-mail do redator de logs (`core/logging.py`, seção 18.1).
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# 2. Onze dígitos, com ou sem os pontos e o hífen do CPF. As bordas impedem casar no meio de
# um número maior.
_CPF = re.compile(r"(?<![\d.\-])\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?![\d\-])")
# 3. De 13 a 19 dígitos, com espaços ou hífens soltos entre eles.
_CARD = re.compile(r"(?<![\d\-])\d(?:[ \-]?\d){12,18}(?![\d])")
# 4. e 5. Um bloco de dígitos e separadores (`+`, `(`, `)`, hífen e espaço), que vai até o
# primeiro caractere que não é dígito nem separador. O bloco termina num dígito, para não
# levar um espaço ou um parêntese que sobra.
_BLOCK = re.compile(r"[+(]*\d(?:[\d+() \-]*\d)?")
# Um bloco que começa com uma data como `10-11-2026`, ou `2026-11-10`, não é telefone (seção
# 29.9.7).
_DATE_START = re.compile(r"(?:\d{1,2}-\d{1,2}-\d{4}|\d{4}-\d{1,2}-\d{1,2})(?!\d)")
_SEPARATORS = frozenset("+() -")
# 5. Seis ou mais dígitos seguidos, como um prontuário ou um telefone sem separador.
_LONG_RUN = re.compile(r"\d{6,}")


@dataclass(frozen=True, slots=True)
class Redacted:
    """O texto já com os marcadores e quantos identificadores de cada tipo saíram."""

    text: str
    counts: dict[IdentifierKind, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        """Quantos identificadores saíram, de todos os tipos. Vai no span `handoff.message`."""
        return sum(self.counts.values())


def redact_identifiers(text: str) -> Redacted:
    """Troca e-mail, CPF válido, cartão que passa no Luhn, telefone e número longo. FR-25.

    1. E-mail.
    2. CPF de 11 dígitos com os dígitos verificadores válidos.
    3. Cartão de 13 a 19 dígitos que passa no algoritmo de Luhn.
    4. Telefone: um bloco de 7 a 15 dígitos com pelo menos um separador entre eles, que não
       começa com uma data.
    5. Número longo: 6 ou mais dígitos seguidos, ou um bloco com mais de 15 dígitos.

    Em cada regra, um trecho que encosta num telefone do catálogo fica como está. Data, hora,
    valor em reais e número de quarto continuam no texto.
    """
    counts: dict[IdentifierKind, int] = {}
    value = text
    # 1.
    value = _apply(value, _EMAIL, lambda _match: IdentifierKind.EMAIL, counts)
    # 2.
    value = _apply(value, _CPF, _cpf_kind, counts)
    # 3.
    value = _apply(value, _CARD, _card_kind, counts)
    # 4. e o bloco longo de 5.
    value = _apply(value, _BLOCK, _block_kind, counts)
    # 5.
    value = _apply(value, _LONG_RUN, lambda _match: IdentifierKind.NUMBER, counts)
    return Redacted(text=value, counts=counts)


def cpf_is_valid(digits: str) -> bool:
    """Os dois dígitos verificadores do CPF conferem, e os 11 dígitos não são todos iguais.

    Um CPF como `111.111.111-11` passa na conta, mas não existe; ele cai na regra do número
    longo, que também o remove.
    """
    if len(digits) != 11 or not digits.isdigit() or len(set(digits)) == 1:
        return False
    numbers = [int(char) for char in digits]
    for position in (9, 10):
        total = sum(numbers[index] * (position + 1 - index) for index in range(position))
        check = (total * 10) % 11 % 10
        if check != numbers[position]:
            return False
    return True


def luhn_is_valid(digits: str) -> bool:
    """O número passa no algoritmo de Luhn, o dígito de controle dos cartões."""
    if not digits.isdigit():
        return False
    total = 0
    for index, char in enumerate(reversed(digits)):
        number = int(char)
        if index % 2 == 1:
            number *= 2
            if number > 9:
                number -= 9
        total += number
    return total % 10 == 0


def _apply(
    text: str,
    pattern: re.Pattern[str],
    classify: Callable[[re.Match[str]], IdentifierKind | None],
    counts: dict[IdentifierKind, int],
) -> str:
    """Roda uma regra no texto e devolve o texto novo, contando cada troca em `counts`.

    Os trechos do catálogo são lidos de novo a cada regra, porque a regra anterior pode ter
    mudado as posições. `classify` devolve o tipo do identificador ou `None` para deixar o
    trecho como está.
    """
    protected = catalog_phone_spans(text)

    def replace(match: re.Match[str]) -> str:
        if _touches(match.span(), protected):
            return match.group(0)
        kind = classify(match)
        if kind is None:
            return match.group(0)
        counts[kind] = counts.get(kind, 0) + 1
        return MARKERS[kind]

    return pattern.sub(replace, text)


def _cpf_kind(match: re.Match[str]) -> IdentifierKind | None:
    """CPF só com os dígitos verificadores válidos; o resto segue para as outras regras."""
    digits = re.sub(r"\D", "", match.group(0))
    return IdentifierKind.CPF if cpf_is_valid(digits) else None


def _card_kind(match: re.Match[str]) -> IdentifierKind | None:
    """Cartão só quando os 13 a 19 dígitos passam no Luhn."""
    digits = re.sub(r"\D", "", match.group(0))
    if not 13 <= len(digits) <= 19:
        return None
    return IdentifierKind.CARD if luhn_is_valid(digits) else None


def _block_kind(match: re.Match[str]) -> IdentifierKind | None:
    """Telefone, número longo ou nada, pelo bloco inteiro (seção 29.9.7).

    Um bloco com mais de 15 dígitos é número longo, mesmo com separadores. Um de 7 a 15 com
    um separador entre os dígitos é telefone, salvo quando começa com uma data. O resto fica
    para a regra dos 6 dígitos seguidos.
    """
    block = match.group(0)
    digits = sum(char.isdigit() for char in block)
    if digits > 15:
        return IdentifierKind.NUMBER
    if not 7 <= digits <= 15:
        return None
    if not any(char in _SEPARATORS for char in block.strip("+(")):
        return None
    if _DATE_START.match(block.lstrip("+(")):
        return None
    return IdentifierKind.PHONE


def _touches(span: tuple[int, int], protected: list[tuple[int, int]]) -> bool:
    """O trecho cruza algum telefone do catálogo."""
    start, end = span
    return any(start < other_end and other_start < end for other_start, other_end in protected)
