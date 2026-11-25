from io import BytesIO
from pathlib import Path

from pypdf import PdfWriter

from app.pdf.profile import classify_page, profile_pages
from app.pdf.text_layer import page_texts

SAMPLE = Path("eval/dataset/sample")


def read(doc: str, variant: str) -> bytes:
    return (SAMPLE / doc / f"{variant}.pdf").read_bytes()


def test_clean_pdf_has_text_and_is_digital():
    data = read("invoice_000", "clean")
    texts = page_texts(data)
    assert "Factura No." in texts[0]
    assert profile_pages(data, texts) == ["digital"]


def test_scanned_variants_have_no_text():
    for variant in ("scanned", "watermark"):
        data = read("resume_000", variant)
        texts = page_texts(data)
        assert texts == [""]
        assert profile_pages(data, texts) == ["scanned"]


def test_blank_page_is_empty():
    writer = PdfWriter()
    writer.add_blank_page(612, 792)
    buf = BytesIO()
    writer.write(buf)
    data = buf.getvalue()
    assert profile_pages(data, page_texts(data)) == ["empty"]


def test_classify_thresholds():
    letter = 612 * 792
    assert classify_page("x" * 30, letter, 0) == "digital"
    assert classify_page("x" * 5, letter, letter) == "scanned"  # algo de ruido sobre una imagen
    assert classify_page("", letter, letter * 0.1) == "empty"  # un logo no hace un escaneo
