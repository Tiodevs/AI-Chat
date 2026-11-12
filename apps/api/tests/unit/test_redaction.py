"""Remoção de identificadores da mensagem do visitante. FR-25, seção 29.9.7 do SDD.

Testa `redact_identifiers` sem banco nem rede: o que sai (e-mail, CPF válido, cartão que
passa no Luhn, telefone e número longo) e o que fica no texto (data, hora, valor em reais,
número de quarto e os telefones do catálogo da seção 9 em qualquer forma reconhecida).
"""

import pytest

from app.domain.redaction import (
    IdentifierKind,
    cpf_is_valid,
    luhn_is_valid,
    redact_identifiers,
)

# Um CPF inventado com os dígitos verificadores certos e um cartão de teste que passa no Luhn.
VALID_CPF = "529.982.247-25"
VALID_CARD = "4111 1111 1111 1111"


def test_email_is_removed() -> None:
    result = redact_identifiers("Meu e-mail é ana.costa@example.com, tá?")
    assert result.text == "Meu e-mail é [e-mail removido], tá?"
    assert result.counts == {IdentifierKind.EMAIL: 1}


@pytest.mark.parametrize("cpf", [VALID_CPF, "52998224725", "529982247-25"])
def test_valid_cpf_is_removed_with_or_without_punctuation(cpf: str) -> None:
    result = redact_identifiers(f"Meu CPF é {cpf}.")
    assert result.text == "Meu CPF é [CPF removido]."
    assert result.counts == {IdentifierKind.CPF: 1}


def test_cpf_with_wrong_check_digits_is_not_called_a_cpf() -> None:
    # Com os pontos e o hífen, nenhum trecho chega a 6 dígitos seguidos: o texto fica.
    result = redact_identifiers("Número 123.456.789-00 inválido")
    assert IdentifierKind.CPF not in result.counts
    assert result.text == "Número 123.456.789-00 inválido"


def test_card_that_passes_luhn_is_removed() -> None:
    result = redact_identifiers(f"Cartão {VALID_CARD} final")
    assert result.text == "Cartão [cartão removido] final"
    assert result.counts == {IdentifierKind.CARD: 1}


@pytest.mark.parametrize(
    "phone",
    ["(11) 98765-4321", "+55 11 98765-4321", "11 98765 4321", "9876-5432"],
)
def test_phone_with_separators_is_removed(phone: str) -> None:
    result = redact_identifiers(f"Me liga no {phone} depois")
    assert result.text == "Me liga no [telefone removido] depois"
    assert result.counts == {IdentifierKind.PHONE: 1}


@pytest.mark.parametrize("number", ["987654", "12345678901234567", "1234 5678 9012 3456 78"])
def test_long_number_is_removed(number: str) -> None:
    result = redact_identifiers(f"Prontuário {number} aqui")
    assert result.text == "Prontuário [número removido] aqui"
    assert result.counts == {IdentifierKind.NUMBER: 1}


@pytest.mark.parametrize(
    "text",
    [
        "A consulta é em 10/11/2026 às 14:30.",
        "A consulta é em 10-11-2026 às 14:30.",
        "Paguei R$ 1.250,90 na farmácia.",
        "Estou no quarto 412, andar 3.",
        "Chego às 08:00 do dia 2026-11-12.",
    ],
)
def test_dates_times_money_and_rooms_stay(text: str) -> None:
    result = redact_identifiers(text)
    assert result.text == text
    assert result.total == 0


@pytest.mark.parametrize(
    "phone",
    ["(555) 014-2600", "555-014-2620", "014-2630", "(555)014-2640"],
)
def test_catalog_phones_stay_in_any_recognized_form(phone: str) -> None:
    text = f"Liguei para {phone} e ninguém atendeu."
    result = redact_identifiers(text)
    assert result.text == text
    assert result.total == 0


def test_rules_run_in_order_and_count_each_kind() -> None:
    text = (
        f"ana@example.com, CPF {VALID_CPF}, cartão {VALID_CARD}, "
        "tel (11) 98765-4321, prontuário 1234567 e a mesa (555) 014-2600"
    )
    result = redact_identifiers(text)
    assert result.text == (
        "[e-mail removido], CPF [CPF removido], cartão [cartão removido], "
        "tel [telefone removido], prontuário [número removido] e a mesa (555) 014-2600"
    )
    assert result.counts == {
        IdentifierKind.EMAIL: 1,
        IdentifierKind.CPF: 1,
        IdentifierKind.CARD: 1,
        IdentifierKind.PHONE: 1,
        IdentifierKind.NUMBER: 1,
    }
    assert result.total == 5


def test_cpf_check_digits() -> None:
    assert cpf_is_valid("52998224725")
    assert not cpf_is_valid("52998224724")
    # Todos iguais passam na conta, mas não são CPF.
    assert not cpf_is_valid("11111111111")


def test_luhn() -> None:
    assert luhn_is_valid("4111111111111111")
    assert not luhn_is_valid("4111111111111112")
