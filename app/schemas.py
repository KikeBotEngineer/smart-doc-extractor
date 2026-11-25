"""Contrato de respuesta de la API."""

from typing import Any, Literal

from pydantic import BaseModel

Confidence = Literal["high", "medium", "low"]
Source = Literal["text_layer", "ocr", "vision", "rule"]
MissingReason = Literal[
    "not_present", "illegible", "insufficient_evidence", "conflicting_candidates"
]


class Evidence(BaseModel):
    page: int
    snippet: str


class FieldResult(BaseModel):
    value: Any = None
    confidence: Confidence | None = None
    source: Source | None = None
    evidence: Evidence | None = None
    missing_reason: MissingReason | None = None


class Validation(BaseModel):
    rule: str
    passed: bool
    detail: str | None = None
