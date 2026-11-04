"""Regras do upload do admin. Seções 7.3 e 10.4, critério CA-1 da Etapa 7.1 (FR-10, NFR-10)."""

from datetime import UTC, datetime, timedelta

from app.domain.documents import (
    MAX_UPLOAD_BYTES,
    UPLOAD_LIMIT,
    AcceptedFile,
    UploadIssue,
    check_file,
    clean_title,
    numbered_slug,
    processing_is_recent,
    slugify,
    upload_rate_decision,
    upload_window_start,
)

NOW = datetime(2026, 11, 4, 10, 20, tzinfo=UTC)


def test_markdown_text_and_pdf_are_accepted_by_extension() -> None:
    assert check_file("Estacionamento.MD", b"# Estacionamento") == AcceptedFile(
        "Estacionamento.MD", "text/markdown"
    )
    assert check_file("notas.txt", "Café às 9h".encode()) == AcceptedFile(
        "notas.txt", "text/plain"
    )
    assert check_file("guia.pdf", b"%PDF-1.7\n...") == AcceptedFile(
        "guia.pdf", "application/pdf"
    )


def test_other_types_are_refused_whatever_the_browser_declares() -> None:
    assert check_file("contrato.docx", b"PK\x03\x04") is UploadIssue.UNSUPPORTED_TYPE
    assert check_file("sem-extensao", b"texto") is UploadIssue.UNSUPPORTED_TYPE
    assert check_file("falso.pdf", b"# Markdown") is UploadIssue.NOT_PDF
    assert check_file("binario.md", b"\xff\xfe\x00") is UploadIssue.NOT_UTF8
    assert check_file("nulo.txt", b"a\x00b") is UploadIssue.NOT_UTF8


def test_the_size_limit_is_ten_megabytes() -> None:
    assert isinstance(check_file("ok.md", b"a" * MAX_UPLOAD_BYTES), AcceptedFile)
    assert check_file("grande.md", b"a" * (MAX_UPLOAD_BYTES + 1)) is UploadIssue.TOO_LARGE
    assert check_file("vazio.md", b"") is UploadIssue.EMPTY


def test_the_stored_filename_drops_any_path() -> None:
    accepted = check_file("C:\\pasta\\sub/04-parking.md", b"# P")
    assert isinstance(accepted, AcceptedFile)
    assert accepted.filename == "04-parking.md"


def test_the_title_falls_back_to_the_file_name() -> None:
    assert clean_title("  Guia   de visitas ", "x.md") == "Guia de visitas"
    assert clean_title(None, "guia_do_acompanhante.pdf") == "guia do acompanhante"
    assert clean_title("x" * 201, "a.md") is UploadIssue.TITLE_TOO_LONG


def test_slugs_are_ascii_and_never_collide() -> None:
    assert slugify("Orientações à Família") == "orientacoes-a-familia"
    assert slugify("!!!") == "documento"
    assert numbered_slug("guia", set()) == "guia"
    assert numbered_slug("guia", {"guia", "guia-2"}) == "guia-3"


def test_uploads_are_limited_to_thirty_per_hour() -> None:
    window = upload_window_start(NOW)
    assert window == datetime(2026, 11, 4, 10, 0, tzinfo=UTC)
    assert not upload_rate_decision(count=UPLOAD_LIMIT, now=NOW, window_start=window).limited
    limited = upload_rate_decision(count=UPLOAD_LIMIT + 1, now=NOW, window_start=window)
    assert limited.limited
    assert limited.retry_after_seconds == 40 * 60


def test_processing_versions_older_than_fifteen_minutes_do_not_block() -> None:
    assert processing_is_recent(NOW - timedelta(minutes=14), NOW)
    assert not processing_is_recent(NOW - timedelta(minutes=15), NOW)
