import json
from pathlib import Path

import pytest

from app.config import Settings
from app.llm.client import LLMResponse
from app.pdf.ocr import group_lines
from app.pipeline import run

SAMPLE = Path("eval/dataset/sample")


class TruthLLM:
    """Responde con el ground truth del documento (con cambios opcionales) y guarda lo que
    recibió."""

    def __init__(self, doc: str, **overrides):
        truth = json.loads((SAMPLE / doc / "ground_truth.json").read_text(encoding="utf-8"))
        self.answer = json.dumps(truth["fields"] | overrides)
        self.prompts, self.images = [], []

    def generate(self, prompt, schema, images=()):
        self.prompts.append(prompt)
        self.images.append(list(images))
        return LLMResponse(self.answer, 100, 10)


def extract(doc: str, variant: str, doc_type: str, **overrides):
    llm = TruthLLM(doc, **overrides)
    data = (SAMPLE / doc / f"{variant}.pdf").read_bytes()
    return run(data, doc_type, llm, Settings()), llm


@pytest.fixture(scope="module")
def scanned_invoice():  # el OCR tarda unos segundos: una sola corrida para varias pruebas
    return extract("invoice_000", "scanned", "invoice", issuer_name="Inventada S.A.")


def test_group_lines_orders_a_table_row():
    def box(x, y):
        return [[x, y], [x + 50, y], [x + 50, y + 20], [x, y + 20]]

    items = [(box(300, 102), "$347.60"), (box(10, 100), "Capacitación"), (box(10, 140), "Total")]
    assert group_lines(items) == ["Capacitación $347.60", "Total"]


def test_scanned_pdf_goes_visual_with_ocr_and_image(scanned_invoice):
    result, llm = scanned_invoice
    assert result.route == "visual"
    assert [p.profile for p in result.pages] == ["scanned"]
    assert len(llm.images[0]) == 1 and llm.images[0][0][:2] == b"\xff\xd8"  # JPEG
    assert "--- Página 1 (OCR) ---" in llm.prompts[0] and "F-77336" in llm.prompts[0]


def test_ocr_evidence(scanned_invoice):
    fields = scanned_invoice[0].fields
    number = fields["invoice_number"]
    assert (number.confidence, number.source, number.evidence.page) == ("high", "ocr", 1)
    assert fields["total"].confidence == "high"
    # el OCR pierde el acento de "Capacitación": evidencia parcial
    description = fields["line_items[0].description"]
    assert (description.confidence, description.source) == ("medium", "ocr")


def test_value_seen_only_by_the_llm_is_low_vision(scanned_invoice):
    issuer = scanned_invoice[0].fields["issuer_name"]
    assert (issuer.value, issuer.confidence, issuer.source, issuer.evidence) == (
        "Inventada S.A.",
        "low",
        "vision",
        None,
    )


def test_watermarked_resume_dates_survive_ocr():
    result, _ = extract("resume_000", "watermark", "resume")
    fields = result.fields
    for path in ("email", "experience[0].start_date", "experience[1].end_date"):
        assert fields[path].confidence == "high", (path, fields[path])
    assert all(v.passed for v in result.validations)
