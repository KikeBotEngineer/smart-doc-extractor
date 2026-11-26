from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfWriter

from app.pdf.ocr import MAX_PIXELS, render_page
from app.pdf.profile import classify_page, profile_pages
from app.pdf.text_layer import page_texts

SAMPLE = Path("eval/dataset/sample")


def read(doc: str, variant: str) -> bytes:
    return (SAMPLE / doc / f"{variant}.pdf").read_bytes()


def blank(width: float, height: float) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width, height)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


# pdfium redondea hacia arriba: cada lado puede tener 1 px de más


def test_render_keeps_dpi_on_normal_pages():
    size = render_page(blank(612, 792), 0).size  # carta a 150 dpi
    assert size == pytest.approx((1275, 1650), abs=1)


def test_render_caps_giant_pages():
    width, height = render_page(blank(14400, 14400), 0).size  # 30,000 px por lado sin tope
    assert (width - 1) * (height - 1) <= MAX_PIXELS


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
    data = blank(612, 792)
    assert profile_pages(data, page_texts(data)) == ["empty"]


def test_classify_thresholds():
    letter = 612 * 792
    assert classify_page("x" * 30, letter, 0) == "digital"
    assert classify_page("x" * 5, letter, letter) == "scanned"  # algo de ruido sobre una imagen
    assert classify_page("", letter, letter * 0.1) == "empty"  # un logo no hace un escaneo
