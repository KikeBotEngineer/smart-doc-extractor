from datetime import date

import pytest

from app.doc_types.invoice import IDENTIFIERS, Invoice, LineItem
from app.evidence import PageText, find_evidence, flatten, parse_number, verify_fields


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("1,160.00", 1160.0),
        ("1.160,00", 1160.0),
        ("1160", 1160.0),
        ("1,160", 1160.0),
        ("12.5", 12.5),
        ("1,234,567.89", 1234567.89),
        ("594.078.1618", None),  # teléfono, no monto
    ],
)
def test_parse_number(token, expected):
    assert parse_number(token) == expected


@pytest.mark.parametrize(
    "text",
    ["Fecha: 22/06/2023", "2023-06-22", "22 de junio de 2023", "22 jun. 2023", "June 22, 2023"],
)
def test_dates_in_common_formats(text):
    assert find_evidence(date(2023, 6, 22), False, [text])[2] is True


def test_wrong_date_is_not_evidence():
    assert find_evidence(date(2023, 6, 21), False, ["22/06/2023"]) is None


@pytest.mark.parametrize("text", ["09/2010", "sep 2010", "septiembre de 2010", "2010-09"])
def test_year_month_formats(text):
    assert find_evidence("2010-09", False, [f"Inicio {text} – Actual"]) is not None


def test_amount_matches_formatted_number():
    page, snippet, literal = find_evidence(1160.0, False, ["Subtotal $1,000.00", "TOTAL $1,160.00"])
    assert (page, literal) == (2, True) and "$1,160.00" in snippet


def test_identifier_is_literal_with_word_boundaries():
    assert find_evidence("a-1042", True, ["Factura No. A-1042"]) is not None  # mayúsculas
    assert find_evidence("A-104", True, ["Factura No. A-1042"]) is None
    assert find_evidence("A-1O42", True, ["Factura No. A-1042"]) is None  # sin difuso


def test_literal_ignores_spaces_lost_by_ocr():
    found = find_evidence("Licencia de software anual", False, ["Licencia desoftware anual 4"])
    assert found[2] is True and "desoftware" in found[1]


def test_free_text_falls_back_to_fuzzy_as_partial_evidence():
    page = "Servicio de consultoria en sitio"
    assert find_evidence("Servicio de consultoría", False, [page])[2] is False
    assert find_evidence("Hosting administrado", False, [page]) is None


ROWS = (  # OCR real de la factura escaneada de la muestra
    "Licencia desoftware anual 4 $1,154.89 $4,619.56\n"
    "Mantenimientopreventivo 9 $480.35 $4,323.15\n"
    "Servicio de consultoria 4 $2,551.51 $10,206.04"
)


def test_repeated_number_takes_the_evidence_from_its_own_row():
    inv = Invoice(
        line_items=[
            LineItem(description="Licencia de software anual", quantity=4, amount=4619.56),
            LineItem(description="Mantenimiento preventivo", quantity=9, amount=4323.15),
            LineItem(description="Servicio de consultoría", quantity=4, amount=10206.04),
        ]
    )
    fields = verify_fields(inv, [PageText(ROWS, "ocr")], "vision", IDENTIFIERS)
    first, last = fields["line_items[0].quantity"], fields["line_items[2].quantity"]
    assert first.confidence == "high" and "anual 4 $1,154.89" in first.evidence.snippet
    assert last.confidence == "high" and "consultoria 4 $2,551.51" in last.evidence.snippet


def test_repeated_number_without_anchors_is_partial():
    inv = Invoice(line_items=[LineItem(quantity=4)])
    fields = verify_fields(inv, [PageText(ROWS)], "text_layer", IDENTIFIERS)
    assert fields["line_items[0].quantity"].confidence == "medium"


def test_single_match_outside_its_row_is_partial():
    text = "Capacitacion en sitio 2 $173.80 $347.60\nLicencia desoftware anual $1,154.89 $4,619.56"
    inv = Invoice(
        line_items=[
            LineItem(description="Capacitacion en sitio", quantity=2, amount=347.6),
            LineItem(description="Licencia desoftware anual", quantity=2, amount=4619.56),
        ]
    )
    fields = verify_fields(inv, [PageText(text)], "text_layer", IDENTIFIERS)
    assert fields["line_items[0].quantity"].confidence == "high"
    assert fields["line_items[1].quantity"].confidence == "medium"  # ese 2 es de otro renglón


def test_flatten():
    data = {"a": 1, "items": [{"x": 1}, {"x": 2}], "tags": ["p"], "empty": []}
    expected = {"a": 1, "items[0].x": 1, "items[1].x": 2, "tags[0]": "p", "empty": None}
    assert flatten(data) == expected


def test_verify_fields_assigns_confidence():
    inv = Invoice(
        invoice_number="A-1042",
        total=1160.0,
        issuer_name="Inventada S.A.",  # el LLM la propuso, pero no está
        line_items=[LineItem(amount=1000.0)],
    )
    text = "Factura No. A-1042\nImporte $1,000.00\nTOTAL $1,160.00"
    fields = verify_fields(inv, [PageText(text)], "text_layer", IDENTIFIERS)
    assert fields["invoice_number"].confidence == "high"
    assert fields["invoice_number"].evidence.page == 1
    assert fields["line_items[0].amount"].confidence == "high"
    hallucinated = fields["issuer_name"]
    assert (hallucinated.value, hallucinated.confidence, hallucinated.evidence) == (
        "Inventada S.A.",
        "low",
        None,
    )
    assert fields["due_date"].missing_reason == "not_present"
    assert fields["due_date"].confidence is None
