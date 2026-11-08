"""Telefones no formato do catálogo da seção 9. Sem I/O.

Camada de domínio. Quem usa: o avaliador `no_unknown_phone` (`app/evals/evaluators.py`), o
script `run_evals`, que monta o catálogo a partir de `docs/sdd/corpus.md`, e
`tests/unit/test_corpus_catalog.py`, que confere que o corpus só cita telefones do catálogo.
Seções 9 e 21.2 do SDD. A conferência de telefone da resposta ao vivo é outra, em
`grounding.py`.
"""

import re

# Três formas: `(555) 014-2600`, `555-014-2600` e o número curto `014-2600`, sem o código de
# área. Todas viram a forma canônica `(555) 014-2600` em `_canonical`.
_PHONE = re.compile(r"\(\s*\d{3}\s*\)\s*\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b|\b014-\d{4}\b")


def phones_in(text: str) -> set[str]:
    """Telefones do texto, na forma canônica `(555) 014-2600`."""
    return {_canonical(match.group(0)) for match in _PHONE.finditer(text)}


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
