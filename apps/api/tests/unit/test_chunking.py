"""O divisor respeita títulos, tamanho e sobreposição. Seção 7.3."""

from app.domain.chunking import CHUNK_SIZE, split_markdown


def test_chunks_do_not_cross_markdown_headings() -> None:
    markdown = (
        "# Entrada\n\nA entrada principal.\n\n# Estacionamento\n\nA garagem da Harbor Street."
    )
    chunks = split_markdown(markdown)
    assert [chunk.heading for chunk in chunks] == ["Entrada", "Estacionamento"]
    assert chunks[0].content == "A entrada principal."
    assert "garagem" not in chunks[0].content
    assert chunks[1].content == "A garagem da Harbor Street."


def test_text_before_the_first_heading_has_no_section() -> None:
    chunks = split_markdown("Antes do título.\n\n# Visitas\n\nHorário geral.")
    assert chunks[0].heading is None
    assert chunks[0].content == "Antes do título."
    assert chunks[1].heading == "Visitas"


def test_long_section_stays_within_the_size_limit_and_overlaps() -> None:
    body = "x" * 1200
    chunks = split_markdown(body, chunk_size=CHUNK_SIZE, overlap=150)
    assert len(chunks) >= 2
    assert all(len(chunk.content) <= CHUNK_SIZE for chunk in chunks)
    assert chunks[0].heading is None
    assert chunks[0].content[-150:] == chunks[1].content[:150]


def test_words_longer_than_a_short_window_still_respect_the_limit() -> None:
    body = " ".join(["palavra"] * 400)
    chunks = split_markdown("# Horários\n\n" + body, chunk_size=1000, overlap=150)
    assert len(chunks) > 1
    assert {chunk.heading for chunk in chunks} == {"Horários"}
    assert all(len(chunk.content) <= 1000 for chunk in chunks)
    assert "Entrada" not in "".join(chunk.content for chunk in chunks)
