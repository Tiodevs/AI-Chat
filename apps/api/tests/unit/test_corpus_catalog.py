"""O catálogo da seção 9 é a única fonte de telefones e horários do corpus. Seções 3.3 e 9.

Lê a tabela de `docs/sdd/corpus.md` com `load_catalog` e confere os doze arquivos de
`content/corpus`: cada um contém os fatos da sua linha, e nenhum cita telefone ou faixa de
horário fora do catálogo. O `content/corpus/README.md` segue a mesma regra (a lista de
cuidados do `CONTRIBUTING.md`). Os três últimos testes conferem o próprio verificador: ele
recusa uma faixa e um telefone inventados e aceita uma faixa do catálogo escrita com hífen. Lê
só arquivos do repositório; não usa banco nem rede.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from app.domain.phones import CATALOG_PHONES, phones_in

ROOT = Path(__file__).resolve().parents[4]
CATALOG_PATH = ROOT / "docs/sdd/corpus.md"
CORPUS_PATH = ROOT / "content/corpus"
EN_DASH = "\u2013"
ROW = re.compile(r"^\| `([^`]+)` \| (.*) \|$")
TIME_RANGE = re.compile(rf"(\d{{2}}:\d{{2}})\s*[{EN_DASH}\u2014-]\s*(\d{{2}}:\d{{2}})")
EXPECTED_FILES = (
    "01-about.md",
    "02-visiting.md",
    "03-wayfinding.md",
    "04-parking.md",
    "05-departments.md",
    "06-appointments.md",
    "07-billing.md",
    "08-access.md",
    "09-privacy.md",
    "10-emergency.md",
    "11-amenities.md",
    "12-feedback.md",
)
PUBLISHED_PHONES = frozenset(
    {
        "(555) 014-2600",
        "(555) 014-2620",
        "(555) 014-2630",
        "(555) 014-2640",
    }
)
PUBLISHED_TIME_RANGES = frozenset(
    {
        f"11:00{EN_DASH}20:00",
        f"13:00{EN_DASH}14:00",
        f"06:00{EN_DASH}20:00",
        f"08:00{EN_DASH}16:30",
        f"06:30{EN_DASH}19:30",
        f"09:00{EN_DASH}18:00",
        f"09:00{EN_DASH}16:00",
    }
)


@dataclass(frozen=True)
class Catalog:
    """A tabela da seção 9: os fatos por arquivo, os telefones e as faixas de horário."""

    facts: dict[str, str]
    phones: frozenset[str]
    time_ranges: frozenset[str]


def test_seed_documents_cover_the_section_9_catalog() -> None:
    catalog = load_catalog(CATALOG_PATH)
    assert tuple(catalog.facts) == EXPECTED_FILES
    assert catalog.phones == PUBLISHED_PHONES
    # A remoção de identificadores do atendimento usa a mesma lista (seção 29.9.7).
    assert catalog.phones == CATALOG_PHONES
    assert catalog.time_ranges == PUBLISHED_TIME_RANGES

    documents = {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(CORPUS_PATH.glob("*.md"))
        if path.name != "README.md"
    }
    assert tuple(documents) == EXPECTED_FILES
    for name, facts in catalog.facts.items():
        assert squash(facts) in squash(documents[name]), name
        assert phones_in(documents[name]) <= catalog.phones
        assert_time_ranges_belong_to_catalog(documents[name], catalog)

    readme = (CORPUS_PATH / "README.md").read_text(encoding="utf-8")
    assert phones_in(readme) <= catalog.phones
    assert_time_ranges_belong_to_catalog(readme, catalog)
    assert phones_in("\n".join(documents.values())) == catalog.phones


def test_invented_time_range_is_rejected_by_the_catalog() -> None:
    catalog = load_catalog(CATALOG_PATH)
    invented = f"Aberto 07:15{EN_DASH}07:45."
    with pytest.raises(AssertionError, match=r"07:15.07:45"):
        assert_time_ranges_belong_to_catalog(invented, catalog)


def test_hyphenated_catalog_range_is_accepted() -> None:
    catalog = load_catalog(CATALOG_PATH)
    assert_time_ranges_belong_to_catalog("Visita 11:00-20:00.", catalog)


def test_invented_phone_is_outside_the_catalog() -> None:
    catalog = load_catalog(CATALOG_PATH)
    assert phones_in("Ramal (555) 014-2699.") - catalog.phones == {"(555) 014-2699"}


def load_catalog(path: Path) -> Catalog:
    """Lê as linhas da tabela, com o arquivo e os fatos, e os telefones e faixas do documento."""
    text = path.read_text(encoding="utf-8")
    facts = {
        match.group(1): match.group(2).strip()
        for line in text.splitlines()
        if (match := ROW.fullmatch(line))
    }
    return Catalog(
        facts=facts,
        phones=frozenset(phones_in(text)),
        time_ranges=frozenset(time_ranges_in(text)),
    )


def time_ranges_in(text: str) -> set[str]:
    """Faixas de horário do texto, com hífen, meia-risca ou travessão, escritas com meia-risca."""
    return {f"{start}{EN_DASH}{end}" for start, end in TIME_RANGE.findall(text)}


def assert_time_ranges_belong_to_catalog(text: str, catalog: Catalog) -> None:
    """Levanta `AssertionError` com as faixas do texto que o catálogo não tem."""
    unknown = sorted(time_ranges_in(text) - set(catalog.time_ranges))
    if unknown:
        raise AssertionError(f"time ranges outside the catalog: {unknown}")


def squash(text: str) -> str:
    """Junta espaços e quebras de linha, para comparar fatos sem depender da formatação."""
    return re.sub(r"\s+", " ", text).strip()
