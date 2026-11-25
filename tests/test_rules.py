import json
from datetime import date
from pathlib import Path

from app.doc_types import DOC_TYPES
from app.doc_types import invoice as inv_rules
from app.doc_types import resume as cv_rules
from app.doc_types.invoice import Invoice, LineItem
from app.doc_types.resume import Education, Experience, Resume
from app.pipeline import run_rules


def item(q, p, a):
    return LineItem(quantity=q, unit_price=p, amount=a)


def test_subtotal_plus_tax_equals_total():
    rule = inv_rules.subtotal_plus_tax_equals_total
    assert rule(Invoice(subtotal=1000, tax=160, total=1160)) == (True, None)
    assert rule(Invoice(subtotal=1000, tax=160, total=1160.01)) == (True, None)  # tolerancia
    passed, detail = rule(Invoice(subtotal=1000, tax=160, total=1200))
    assert not passed and "1160" in detail
    assert rule(Invoice(subtotal=1000, total=1160)) is None  # sin impuestos no se evalúa


def test_line_items_sum_to_subtotal():
    rule = inv_rules.line_items_sum_to_subtotal
    items = [item(1, 0.1, 0.1), item(1, 0.2, 0.2)]  # 0.1 + 0.2 != 0.3 en float
    assert rule(Invoice(line_items=items, subtotal=0.3)) == (True, None)
    assert rule(Invoice(line_items=items, subtotal=1))[0] is False
    assert rule(Invoice(line_items=[LineItem(amount=None)], subtotal=1)) is None


def test_line_amount_consistency_points_to_the_bad_item():
    rule = inv_rules.line_amount_consistency
    inv = Invoice(line_items=[item(2, 173.8, 347.6), item(3, 10, 31), LineItem(description="x")])
    assert rule(inv) == (False, "line_items[1]")
    assert rule(Invoice(line_items=[item(4, 1154.89, 4619.56)])) == (True, None)


def test_due_after_issue():
    rule = inv_rules.due_after_issue
    assert rule(Invoice(issue_date=date(2024, 1, 1), due_date=date(2024, 1, 31)))[0]
    assert not rule(Invoice(issue_date=date(2024, 2, 1), due_date=date(2024, 1, 31)))[0]
    assert rule(Invoice(issue_date=date(2024, 1, 1))) is None


def test_tax_id_format():
    rule = inv_rules.tax_id_format
    assert rule(Invoice(issuer_tax_id="EXD410411Y5R", receiver_tax_id="GODE561231GR8")) == (
        True,
        None,
    )
    assert rule(Invoice(issuer_tax_id="EXD410411Y5R", receiver_tax_id="ABC123")) == (
        False,
        "receiver_tax_id: ABC123",
    )
    assert rule(Invoice()) is None


def test_email_format():
    assert cv_rules.email_format(Resume(email="ana@mail.com")) == (True, None)
    assert cv_rules.email_format(Resume(email="ana@mail")) == (False, "ana@mail")


def test_experience_dates_ordered():
    cv = Resume(
        experience=[
            Experience(start_date="2020-01", end_date="2022-06"),
            Experience(start_date="2019-05", end_date="2018-01"),
            Experience(start_date="2015-01"),  # puesto actual: no se evalúa
        ]
    )
    assert cv_rules.experience_dates_ordered(cv) == (False, "experience[1]")


def test_no_future_dates():
    today = date(2025, 6, 15)
    cv = Resume(
        experience=[Experience(start_date="2025-06"), Experience(end_date="2025-07")],
        education=[Education(graduation_year=2026)],
    )
    assert cv_rules.no_future_dates(cv, today) == (
        False,
        "experience[1].end_date, education[0].graduation_year",
    )
    assert cv_rules.no_future_dates(Resume(), today) is None


def test_sample_documents_pass_all_rules():
    for name, kind in (("invoice_000", "invoice"), ("resume_000", "resume")):
        path = Path("eval/dataset/sample") / name / "ground_truth.json"
        doc = DOC_TYPES[kind].MODEL.model_validate(
            json.loads(path.read_text(encoding="utf-8"))["fields"]
        )
        validations = run_rules(DOC_TYPES[kind].RULES, doc)
        assert validations and all(v.passed for v in validations), validations
