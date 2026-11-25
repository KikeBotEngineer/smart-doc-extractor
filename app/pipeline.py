"""Orquestación del pipeline."""

import time
from collections.abc import Callable, Iterable
from dataclasses import asdict
from io import BytesIO
from pathlib import Path

from pydantic import BaseModel
from pypdf import PasswordType, PdfReader

from app.config import Settings
from app.doc_types import DOC_TYPES
from app.evidence import verify_fields
from app.llm.client import LLMClient, Usage, generate_structured
from app.pdf.profile import profile_pages
from app.pdf.text_layer import page_texts
from app.schemas import DocTypeResult, ExtractResponse, PageInfo, UsageReport, Validation

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"


class RejectedInput(Exception):
    """La entrada no se puede procesar; `status_code` es el código HTTP que corresponde."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def validate_input(data: bytes, settings: Settings) -> None:
    """Etapa 1: tamaño, firma PDF, contraseña y número de páginas."""
    if len(data) > settings.max_file_mb * 1024 * 1024:
        raise RejectedInput(413, f"el archivo supera {settings.max_file_mb} MB")
    if b"%PDF-" not in data[:1024]:
        raise RejectedInput(415, "el archivo no es un PDF")
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted and reader.decrypt("") == PasswordType.NOT_DECRYPTED:
            raise RejectedInput(422, "el PDF está protegido con contraseña")
        pages = len(reader.pages)
    except RejectedInput:
        raise
    except Exception as e:  # entrada no confiable: cualquier fallo de lectura es un PDF dañado
        raise RejectedInput(422, "el PDF está dañado o no se puede leer") from e
    if pages > settings.max_pages:
        raise RejectedInput(422, f"el PDF tiene {pages} páginas; el máximo es {settings.max_pages}")


def render_document(texts: list[str]) -> str:
    """Texto por página con su número; las páginas sin texto se omiten."""
    return "\n\n".join(
        f"--- Página {n} ---\n{text.strip()}" for n, text in enumerate(texts, 1) if text.strip()
    )


def extract_fast(llm: LLMClient, doc_type: str, texts: list[str], usage: Usage) -> BaseModel:
    """Ruta fast: Gemini sobre la capa de texto."""
    kind = DOC_TYPES[doc_type]
    template = (PROMPTS / "extract.md").read_text(encoding="utf-8")
    prompt = template.format(label=kind.LABEL, document=render_document(texts))
    return generate_structured(llm, prompt, kind.MODEL, usage)


def run_rules(rules: Iterable[Callable], doc: BaseModel) -> list[Validation]:
    """Etapa 8. Las reglas sin datos suficientes no se reportan."""
    validations = []
    for rule in rules:
        if (result := rule(doc)) is not None:
            passed, detail = result
            validations.append(Validation(rule=rule.__name__, passed=passed, detail=detail))
    return validations


def run(data: bytes, doc_type: str | None, llm: LLMClient, settings: Settings) -> ExtractResponse:
    started = time.perf_counter()
    validate_input(data, settings)
    if doc_type is None:  # temporal: la clasificación llega en la etapa 4
        raise RejectedInput(422, "doc_type es requerido por ahora")
    texts = page_texts(data)
    profiles = profile_pages(data, texts)
    if all(p == "empty" for p in profiles):
        raise RejectedInput(422, "el PDF no tiene contenido")
    if "scanned" in profiles:  # temporal: la ruta visual llega en la etapa 4
        raise RejectedInput(501, "el PDF tiene páginas escaneadas; la ruta visual aún no existe")
    kind = DOC_TYPES[doc_type]
    usage = Usage()
    doc = extract_fast(llm, doc_type, texts, usage)
    return ExtractResponse(
        doc_type=DocTypeResult(value=doc_type, method="forced", confidence="high"),
        route="fast",
        pages=[PageInfo(page=n, profile=p) for n, p in enumerate(profiles, 1)],
        fields=verify_fields(doc, texts, "text_layer", kind.IDENTIFIERS),
        validations=run_rules(kind.RULES, doc),
        usage=UsageReport(
            **asdict(usage), latency_ms=round((time.perf_counter() - started) * 1000)
        ),
    )
