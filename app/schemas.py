"""Contrato de respuesta de la API."""

from typing import Any, Literal

from pydantic import BaseModel

from app.pdf.profile import PageProfile

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


class DocTypeResult(BaseModel):
    value: str
    method: Literal["keywords", "llm", "forced"]
    confidence: Confidence


class PageInfo(BaseModel):
    page: int
    profile: PageProfile


class UsageReport(BaseModel):
    llm_calls: int
    input_tokens: int
    output_tokens: int
    latency_ms: int


class ExtractResponse(BaseModel):
    doc_type: DocTypeResult
    route: Literal["fast", "visual"]
    pages: list[PageInfo]
    fields: dict[str, FieldResult]
    validations: list[Validation]
    usage: UsageReport
