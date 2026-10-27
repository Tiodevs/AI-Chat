"""Citação válida e telefone presente no contexto. Seção 7.1."""

from uuid import UUID

from app.domain.grounding import ContextBlock, check_grounding

_CHUNK = UUID("00000000-0000-4000-8000-000000000001")


def test_phone_outside_context_fails_even_with_a_valid_citation() -> None:
    decision = check_grounding(
        "Ligue (555) 019-9999 [1].",
        (_block("Mesa (555) 014-2600."),),
    )
    assert decision.grounded is False
    assert decision.citations == ()


def test_phone_in_the_context_keeps_the_citation() -> None:
    decision = check_grounding(
        "Ligue (555) 014-2600 [1].",
        (_block("Mesa (555) 014-2600."),),
    )
    assert decision.grounded is True
    assert [citation.index for citation in decision.citations] == [1]
    assert decision.citations[0].chunk_id == _CHUNK
    assert decision.citations[0].document_title == "Visitas"


def test_phone_matches_when_only_the_digits_are_the_same() -> None:
    decision = check_grounding(
        "Ligue 555 014 2600 [1].",
        (_block("Mesa (555) 014-2600."),),
    )
    assert decision.grounded is True


def test_one_missing_phone_fails_the_draft() -> None:
    decision = check_grounding(
        "Mesa (555) 014-2600 ou direto (555) 019-9999 [1].",
        (_block("Mesa (555) 014-2600."),),
    )
    assert decision.grounded is False


def test_answer_without_a_citation_fails() -> None:
    decision = check_grounding("O horário é 11:00.", (_block("11:00 às 20:00."),))
    assert decision.grounded is False
    assert decision.citations == ()


def test_unknown_citation_index_fails() -> None:
    decision = check_grounding("Veja [2].", (_block("11:00 às 20:00."),))
    assert decision.grounded is False


def test_only_valid_citations_remain() -> None:
    decision = check_grounding(
        "Horário [1] e outro [3].",
        (_block("11:00 às 20:00."), _block("Estacionamento.", index=2, title="Acesso")),
    )
    assert decision.grounded is True
    assert [citation.index for citation in decision.citations] == [1]


def test_repeated_citation_is_kept_once() -> None:
    decision = check_grounding("Veja [1] e de novo [1].", (_block("11:00 às 20:00."),))
    assert [citation.index for citation in decision.citations] == [1]


def _block(content: str, *, index: int = 1, title: str = "Visitas") -> ContextBlock:
    return ContextBlock(
        index=index,
        chunk_id=_CHUNK,
        document_title=title,
        heading="Horário",
        content=content,
    )
