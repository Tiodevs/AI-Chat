"""Prefixos da seção 8.3 e o vetor determinístico."""

import math

from app.adapters.deterministic_embedding import DeterministicEmbeddingProvider
from app.domain.embedding_text import document_embedding_text, query_embedding_text
from app.prompts.corpus import NONE_EMBEDDED, seed_message


def test_embedding_prefixes_match_section_8_3() -> None:
    assert document_embedding_text("Visitas", "Horário", "11:00–20:00.") == (
        "title: Visitas | text: Horário\n11:00–20:00."
    )
    assert document_embedding_text("Visitas", None, "11:00–20:00.") == (
        "title: Visitas | text: 11:00–20:00."
    )
    assert query_embedding_text("Qual é o horário de visita?") == (
        "task: question answering | query: Qual é o horário de visita?"
    )


def test_deterministic_embedding_is_a_stable_unit_vector() -> None:
    provider = DeterministicEmbeddingProvider()

    async def _embed() -> None:
        first = await provider.embed_query("visita")
        again = await provider.embed_documents(["visita", "estacionamento"])
        assert again[0] == first
        assert again[0] != again[1]
        assert len(first) == 768
        norm = math.sqrt(sum(value * value for value in first))
        assert abs(norm - 1.0) < 1e-9

    import asyncio

    asyncio.run(_embed())


def test_second_seed_message_says_nothing_was_embedded() -> None:
    assert seed_message(0) == NONE_EMBEDDED
    assert seed_message(0) == "Nenhum documento foi embedado."
    assert seed_message(2) == "Documentos embedados: 2"
