"""Factura: modelo de extracción, palabras clave de clasificación y reglas."""

import re
from datetime import date

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str | None = Field(None, description="Descripción del concepto")
    quantity: float | None = Field(None, description="Cantidad")
    unit_price: float | None = Field(None, description="Precio unitario")
    amount: float | None = Field(None, description="Importe de la partida")


class Invoice(BaseModel):
    issuer_name: str | None = Field(None, description="Nombre o razón social del emisor")
    issuer_tax_id: str | None = Field(None, description="RFC del emisor")
    receiver_name: str | None = Field(None, description="Nombre o razón social del receptor")
    receiver_tax_id: str | None = Field(None, description="RFC del receptor")
    invoice_number: str | None = Field(None, description="Número o folio de la factura")
    issue_date: date | None = Field(None, description="Fecha de emisión")
    due_date: date | None = Field(None, description="Fecha de vencimiento")
    currency: str | None = Field(None, description="Moneda en código ISO 4217, p. ej. MXN")
    line_items: list[LineItem] = Field(default_factory=list, description="Partidas")
    subtotal: float | None = Field(None, description="Subtotal antes de impuestos")
    tax: float | None = Field(None, description="Total de impuestos")
    total: float | None = Field(None, description="Total a pagar")


LABEL = "factura"
MODEL = Invoice
IDENTIFIERS = {"issuer_tax_id", "receiver_tax_id", "invoice_number", "currency"}
KEYWORDS = ("factura", "invoice", "folio", "rfc", "subtotal", "iva", "importe", "cfdi")
# Etiquetas que preceden a montos y fechas: sin la suya justo antes, la evidencia es parcial
# (un total = 16 no se confirma con "IVA 16%", ni una fecha de emisión con el vencimiento)
LABELS = {
    "subtotal": ("subtotal",),
    "tax": ("iva", "impuesto", "tax"),
    "total": ("total",),
    "issue_date": ("fecha", "emisión", "expedición", "issue date", "invoice date"),
    "due_date": ("vencimiento", "vence", "límite", "due"),
}


# Reglas: devuelven (passed, detail) o None si faltan los datos para evaluarlas.
# Informan, no corrigen: si el total no cuadra, el documento puede estar mal.
Result = tuple[bool, str | None] | None
TOLERANCE = 0.01
RFC = re.compile(r"[A-ZÑ&]{3,4}\d{6}[A-Z\d]{3}")  # 12 caracteres (moral) o 13 (física)


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= TOLERANCE + 1e-9


def subtotal_plus_tax_equals_total(inv: Invoice) -> Result:
    if None in (inv.subtotal, inv.tax, inv.total):
        return None
    expected = round(inv.subtotal + inv.tax, 2)
    ok = _close(expected, inv.total)
    return ok, None if ok else f"{inv.subtotal} + {inv.tax} = {expected}; total = {inv.total}"


def line_items_sum_to_subtotal(inv: Invoice) -> Result:
    amounts = [i.amount for i in inv.line_items]
    if not amounts or None in amounts or inv.subtotal is None:
        return None
    total = round(sum(amounts), 2)
    ok = _close(total, inv.subtotal)
    return ok, None if ok else f"suma de importes = {total}; subtotal = {inv.subtotal}"


def line_amount_consistency(inv: Invoice) -> Result:
    items = [
        (n, i)
        for n, i in enumerate(inv.line_items)
        if None not in (i.quantity, i.unit_price, i.amount)
    ]
    if not items:
        return None
    bad = [f"line_items[{n}]" for n, i in items if not _close(i.quantity * i.unit_price, i.amount)]
    return not bad, ", ".join(bad) or None


def due_after_issue(inv: Invoice) -> Result:
    if inv.issue_date is None or inv.due_date is None:
        return None
    ok = inv.due_date >= inv.issue_date
    return ok, None if ok else f"vencimiento {inv.due_date} < emisión {inv.issue_date}"


def tax_id_format(inv: Invoice) -> Result:
    ids = {k: v for k in ("issuer_tax_id", "receiver_tax_id") if (v := getattr(inv, k))}
    if not ids:
        return None
    bad = [f"{k}: {v}" for k, v in ids.items() if not RFC.fullmatch(v.strip().upper())]
    return not bad, ", ".join(bad) or None


RULES = (
    subtotal_plus_tax_equals_total,
    line_items_sum_to_subtotal,
    line_amount_consistency,
    due_after_issue,
    tax_id_format,
)
