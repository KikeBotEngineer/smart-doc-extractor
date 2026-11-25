import json

import pypdfium2 as pdfium

from app.doc_types.invoice import Invoice
from app.doc_types.resume import Resume
from scripts.generate_dataset import generate


def text_of(path) -> str:
    pdf = pdfium.PdfDocument(path)
    try:
        return "".join(page.get_textpage().get_text_range() for page in pdf)
    finally:
        pdf.close()


def test_generates_variants_and_valid_ground_truth(tmp_path):
    generate(tmp_path, invoices=1, resumes=1)
    for kind, model, key in (("invoice", Invoice, "invoice_number"), ("resume", Resume, "name")):
        doc_dir = tmp_path / f"{kind}_000"
        truth = json.loads((doc_dir / "ground_truth.json").read_text(encoding="utf-8"))
        assert truth["doc_type"] == kind
        doc = model.model_validate(truth["fields"])
        assert getattr(doc, key) in text_of(doc_dir / "clean.pdf")
        for variant in ("scanned", "watermark"):
            assert text_of(doc_dir / f"{variant}.pdf").strip() == ""  # sin capa de texto


def test_invoice_totals_are_consistent(tmp_path):
    generate(tmp_path, invoices=5, resumes=0, seed=7)
    for doc_dir in tmp_path.iterdir():
        inv = Invoice.model_validate(
            json.loads((doc_dir / "ground_truth.json").read_text(encoding="utf-8"))["fields"]
        )
        assert abs(sum(i.amount for i in inv.line_items) - inv.subtotal) <= 0.01
        assert abs(inv.subtotal + inv.tax - inv.total) <= 0.01
