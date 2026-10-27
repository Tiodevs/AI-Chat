"""Extração de Markdown, texto e PDF. Seção 7.3."""

import asyncio
from io import BytesIO

from pypdf import PdfReader

from app.adapters.text_extractor import FileTextExtractor, extract_text


def test_markdown_and_plain_text_are_utf8() -> None:
    assert extract_text(b"visita", "text/markdown") == "visita"
    assert extract_text(b"texto", "text/plain") == "texto"


def test_pdf_text_is_extracted() -> None:
    data = _pdf("Visita ao hospital")
    assert "Visita ao hospital" in extract_text(data, "application/pdf")


def test_async_extractor_reads_plain_text() -> None:
    async def _run() -> None:
        assert await FileTextExtractor().extract(b"visita", "text/plain") == "visita"

    asyncio.run(_run())


def _pdf(text: str) -> bytes:
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({safe}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode())
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    assert PdfReader(BytesIO(bytes(output))).pages
    return bytes(output)
