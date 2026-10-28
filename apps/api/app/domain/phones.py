"""Telefones no formato do catálogo da seção 9. Sem I/O."""

import re

_PHONE = re.compile(r"\(\s*\d{3}\s*\)\s*\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b|\b014-\d{4}\b")


def phones_in(text: str) -> set[str]:
    return {_canonical(match.group(0)) for match in _PHONE.finditer(text)}


def unknown_phones(text: str, catalog: frozenset[str]) -> set[str]:
    return phones_in(text) - set(catalog)


def _canonical(raw: str) -> str:
    compact = re.sub(r"\s+", "", raw)
    if re.fullmatch(r"014-\d{4}", compact):
        return f"(555) {compact}"
    digits = re.sub(r"\D", "", raw)
    return f"({digits[0:3]}) {digits[3:6]}-{digits[6:10]}"
