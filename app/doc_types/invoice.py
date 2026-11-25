"""Factura: modelo de extracción y palabras clave de clasificación."""

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
