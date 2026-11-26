import json
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.config import Settings
from app.llm.client import LLMError
from app.llm.recorded import RecordedLLM
from app.main import app, get_llm, get_settings, slots

SAMPLE = Path("eval/dataset/sample")
TRUTH = json.loads((SAMPLE / "invoice_000" / "ground_truth.json").read_text(encoding="utf-8"))[
    "fields"
]
# la factura de la muestra es invoice_000 del dataset: se usan sus grabaciones, que no
# dependen del texto exacto que extraiga pypdf
RECORDINGS = Path("eval/recordings/invoice_000/clean")


class FailingLLM:
    def generate(self, prompt, schema, images=()):
        raise LLMError("Gemini no responde")


@pytest.fixture
def client():
    # api_key explícito: un API_KEY en el .env local no debe cambiar las pruebas
    app.dependency_overrides[get_settings] = lambda: Settings(llm_mode="recorded", api_key=None)
    app.dependency_overrides[get_llm] = lambda: RecordedLLM(RECORDINGS, sequential=True)
    yield TestClient(app)
    app.dependency_overrides.clear()


def blank_pdf(pages: int = 1, password: str | None = None) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(612, 792)
    if password:
        writer.encrypt(user_password=password)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def post(client, data: bytes, doc_type: str | None = "invoice"):
    form = {"doc_type": doc_type} if doc_type else {}
    return client.post("/extract", files={"file": ("doc.pdf", data, "application/pdf")}, data=form)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_doc_types_come_from_the_models(client):
    types = client.get("/doc-types").json()
    assert set(types) == {"invoice", "resume"}
    assert "subtotal_plus_tax_equals_total" in types["invoice"]["rules"]
    assert "invoice_number" in types["invoice"]["fields"]["properties"]


def test_extract_clean_invoice(client):
    r = post(client, (SAMPLE / "invoice_000" / "clean.pdf").read_bytes())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["doc_type"] == {"value": "invoice", "method": "forced", "confidence": "high"}
    assert body["route"] == "fast"
    assert body["pages"] == [{"page": 1, "profile": "digital"}]
    expected = TRUTH["invoice_number"]
    number = body["fields"]["invoice_number"]
    assert number["value"] == expected and number["confidence"] == "high"
    assert number["source"] == "text_layer" and expected in number["evidence"]["snippet"]
    assert body["fields"]["issue_date"]["value"] == TRUTH["issue_date"]
    assert body["validations"] and all(v["passed"] for v in body["validations"])
    assert body["usage"]["llm_calls"] == 1 and body["usage"]["input_tokens"] > 0


def test_too_large_is_413(client):
    assert post(client, b"%PDF-" + b"0" * (10 * 1024 * 1024)).status_code == 413


def test_not_a_pdf_is_415(client):
    assert post(client, b"hola, no soy un PDF").status_code == 415


@pytest.mark.parametrize(
    ("data", "doc_type", "detail"),
    [
        (blank_pdf(pages=21), "invoice", "21 páginas"),
        (blank_pdf(password="secreta"), "invoice", "contraseña"),
        (b"%PDF-1.7 basura", "invoice", "dañado"),
        (blank_pdf(), "invoice", "no tiene contenido"),
    ],
)
def test_invalid_input_is_422(client, data, doc_type, detail):
    r = post(client, data, doc_type)
    assert r.status_code == 422 and detail in r.json()["detail"]


def test_unknown_doc_type_is_422(client):
    assert post(client, blank_pdf(), "contrato").status_code == 422


def test_api_key_is_required_when_configured(client):
    app.dependency_overrides[get_settings] = lambda: Settings(llm_mode="recorded", api_key="k1")
    pdf = (SAMPLE / "invoice_000" / "clean.pdf").read_bytes()
    files = {"file": ("doc.pdf", pdf, "application/pdf")}
    assert client.post("/extract", files=files).status_code == 401
    assert client.post("/extract", files=files, headers={"X-API-Key": "otra"}).status_code == 401
    ok = client.post(
        "/extract", files=files, data={"doc_type": "invoice"}, headers={"X-API-Key": "k1"}
    )
    assert ok.status_code == 200, ok.text
    assert client.get("/health").status_code == 200  # el health check no pide key


def test_busy_is_503(client):
    slot = slots(Settings().max_concurrent)
    held = 0
    while slot.acquire(blocking=False):  # ocupa todos los lugares
        held += 1
    try:
        r = post(client, (SAMPLE / "invoice_000" / "clean.pdf").read_bytes())
        assert r.status_code == 503 and r.headers["Retry-After"]
    finally:
        for _ in range(held):
            slot.release()


def test_llm_failure_is_502(client):
    app.dependency_overrides[get_llm] = FailingLLM
    r = post(client, (SAMPLE / "invoice_000" / "clean.pdf").read_bytes())
    assert r.status_code == 502 and "Gemini" in r.json()["detail"]


def test_extract_without_doc_type_classifies_by_keywords(client):
    r = post(client, (SAMPLE / "invoice_000" / "clean.pdf").read_bytes(), doc_type=None)
    assert r.status_code == 200, r.text
    assert r.json()["doc_type"] == {"value": "invoice", "method": "keywords", "confidence": "high"}
    assert r.json()["usage"]["llm_calls"] == 1  # sin llamada de clasificación
