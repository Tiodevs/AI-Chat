"""Telefones no formato do catálogo da seção 9. Sem I/O.

Camada de domínio. Quem usa: o avaliador `no_unknown_phone` (`app/evals/evaluators.py`), o
script `run_evals`, que monta o catálogo a partir de `docs/sdd/corpus.md`,
`tests/unit/test_corpus_catalog.py`, que confere que o corpus só cita telefones do catálogo, e
`domain/redaction.py`, que deixa os telefones do catálogo no atendimento (seção 29.9.7).
Seções 9 e 21.2 do SDD. A conferência de telefone da resposta ao vivo é outra, em
`grounding.py`.
"""

import re

# Os quatro telefones publicados no catálogo da seção 9. A remoção de identificadores do
# atendimento os deixa no texto (seção 29.9.7), e `tests/unit/test_corpus_catalog.py` confere
# que a lista bate com a tabela de `docs/sdd/corpus.md`.
CATALOG_PHONES = frozenset(
    {
        "(555) 014-2600",
        "(555) 014-2620",
        "(555) 014-2630",
        "(555) 014-2640",
    }
)

# Três formas: `(555) 014-2600`, `555-014-2600` e o número curto `014-2600`, sem o código de
# área. Todas viram a forma canônica `(555) 014-2600` em `_canonical`.
_PHONE = re.compile(r"\(\s*\d{3}\s*\)\s*\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b|\b014-\d{4}\b")


def phones_in(text: str) -> set[str]:
    """Telefones do texto, na forma canônica `(555) 014-2600`."""
    return {_canonical(match.group(0)) for match in _PHONE.finditer(text)}


def catalog_phone_spans(text: str) -> list[tuple[int, int]]:
    """Início e fim de cada telefone do catálogo no texto, em qualquer das três formas.

    `domain/redaction.py` usa os trechos para não remover um telefone publicado.
    """
    return [
        match.span()
        for match in _PHONE.finditer(text)
        if _canonical(match.group(0)) in CATALOG_PHONES
    ]


def unknown_phones(text: str, catalog: frozenset[str]) -> set[str]:
    """Telefones do texto que não estão no catálogo."""
    return phones_in(text) - set(catalog)


def _canonical(raw: str) -> str:
    """Forma canônica de um telefone.

    O número curto ganha o código de área 555, o único do catálogo. Nos outros, os dez dígitos
    são regrupados como `(ddd) ddd-dddd`.
    """
    compact = re.sub(r"\s+", "", raw)
    if re.fullmatch(r"014-\d{4}", compact):
        return f"(555) {compact}"
    digits = re.sub(r"\D", "", raw)
    return f"({digits[0:3]}) {digits[3:6]}-{digits[6:10]}"
