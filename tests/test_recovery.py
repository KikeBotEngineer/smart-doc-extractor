import json

import pytest

from app.doc_types import invoice
from app.doc_types.invoice import Invoice, LineItem
from app.evidence import PageText, verify_fields
from app.llm.client import LLMError, LLMResponse, Usage
from app.pipeline import recover, with_field

PAGE = [PageText("Factura No. A-1042\nPartida 1 importe $1,000.00\nTOTAL $1,160.00")]


class RecoveryLLM:
    def __init__(self, answer):
        self.answer, self.prompts = answer, []

    def generate(self, prompt, schema, images=()):
        self.prompts.append(prompt)
        if isinstance(self.answer, Exception):
            raise self.answer
        fields = [{"field": k, "value": v} for k, v in self.answer.items()]
        return LLMResponse(json.dumps({"fields": fields}), 50, 5)


def run_recovery(doc: Invoice, answer, page=PAGE):
    llm, usage = RecoveryLLM(answer), Usage()
    fields = verify_fields(doc, page, "text_layer", invoice.IDENTIFIERS)
    doc, fields = recover(llm, invoice, doc, fields, page, [], "text_layer", usage)
    return doc, fields, llm, usage


def test_nothing_pending_means_no_second_call():
    _, _, llm, usage = run_recovery(Invoice(invoice_number="A-1042"), {})
    assert llm.prompts == [] and usage.llm_calls == 0


def test_only_fields_without_evidence_are_asked():
    doc = Invoice(invoice_number="A-1042", total=1100.0, issuer_name="Fantasma")
    _, _, llm, _ = run_recovery(doc, {})
    listing = llm.prompts[0].split("Campos (nombre: valor propuesto):")[1].split("Documento:")[0]
    assert "- total: 1100.0" in listing and '- issuer_name: "Fantasma"' in listing
    assert "invoice_number" not in listing


def test_recovered_value_with_evidence_replaces_the_old_one():
    doc, fields, _, usage = run_recovery(Invoice(total=1100.0), {"total": "1160.00"})
    assert doc.total == 1160.0  # las reglas ven el valor corregido
    assert (fields["total"].value, fields["total"].confidence) == (1160.0, "high")
    assert usage.llm_calls == 1


def test_null_means_insufficient_evidence():
    doc, fields, _, _ = run_recovery(Invoice(issuer_name="Fantasma"), {"issuer_name": None})
    assert doc.issuer_name is None
    assert (fields["issuer_name"].value, fields["issuer_name"].missing_reason) == (
        None,
        "insufficient_evidence",
    )


def test_same_unverified_value_stays_low():
    doc, fields, _, _ = run_recovery(Invoice(issuer_name="Fantasma"), {"issuer_name": "Fantasma"})
    assert doc.issuer_name == "Fantasma" and fields["issuer_name"].confidence == "low"


def test_different_unverified_value_is_a_conflict():
    doc, fields, _, _ = run_recovery(Invoice(issuer_name="Fantasma"), {"issuer_name": "Espectro"})
    assert doc.issuer_name is None
    assert fields["issuer_name"].missing_reason == "conflicting_candidates"


def test_nested_field_and_unrequested_fields():
    doc = Invoice(invoice_number="X-1", line_items=[LineItem(amount=999.0)])
    answer = {"line_items[0].amount": "1000", "invoice_number": "Z-9", "tax": "160"}
    doc, fields, _, _ = run_recovery(doc, answer)
    assert doc.line_items[0].amount == 1000.0
    assert fields["line_items[0].amount"].confidence == "high"
    assert doc.tax is None  # no se pidió: se ignora


def test_value_of_the_wrong_type_is_ignored():
    doc, fields, _, _ = run_recovery(Invoice(total=1100.0), {"total": "mil"})
    assert doc.total == 1100.0 and fields["total"].confidence == "low"


@pytest.mark.parametrize(
    "failure",
    [LLMError("caído"), {"total": 1160}],  # 1160 no es texto: no cumple el esquema
)
def test_failed_recovery_keeps_the_first_pass(failure):
    doc, fields, _, _ = run_recovery(Invoice(total=1100.0), failure)
    assert doc.total == 1100.0 and fields["total"].confidence == "low"


def test_with_field_validates():
    assert with_field(Invoice, Invoice(), "line_items", "no es lista") is None
    assert with_field(Invoice, Invoice(), "currency", "MXN").currency == "MXN"


TWO_ROWS = [  # la cantidad de la segunda partida se perdió en el OCR
    PageText(
        "Capacitacion en sitio 2 $173.80 $347.60\nLicencia desoftware anual $1,154.89 $4,619.56"
    )
]
ITEMS = [
    LineItem(description="Capacitacion en sitio", quantity=2, amount=347.6),
    LineItem(description="Licencia desoftware anual", quantity=4, amount=4619.56),
]


def test_prompt_gives_row_context_and_zero_based_indexes():
    _, _, llm, _ = run_recovery(Invoice(line_items=ITEMS), {}, TWO_ROWS)
    assert "empiezan en 0" in llm.prompts[0]
    expected = '- line_items[1].quantity: 4.0 (misma partida: {"description": "Licencia'
    assert expected in llm.prompts[0]


def test_recovered_number_from_another_row_is_not_trusted():
    # el LLM contó desde 1 y respondió el 2 de la partida 0
    doc, fields, _, _ = run_recovery(
        Invoice(line_items=ITEMS), {"line_items[1].quantity": "2"}, TWO_ROWS
    )
    assert fields["line_items[1].quantity"].missing_reason == "conflicting_candidates"
    assert doc.line_items[1].quantity is None
