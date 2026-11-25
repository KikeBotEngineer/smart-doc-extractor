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
from app.evidence import PageText, verify_fields
from app.llm.client import LLMClient, Usage, generate_structured
from app.pdf.ocr import ocr_image, render_pages, to_jpeg
from app.pdf.profile import PageProfile, profile_pages
from app.pdf.text_layer import page_texts
from app.schemas import DocTypeResult, ExtractResponse, PageInfo, UsageReport, Validation

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
OCR_MIN_SCORE = 0.9  # por debajo, la evidencia OCR de la página cuenta como parcial


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


def prompt(name: str) -> str:
    return (PROMPTS / name).read_text(encoding="utf-8")


def read_pages(
    data: bytes, texts: list[str], profiles: list[PageProfile]
) -> tuple[list[PageText], list[tuple[int, bytes]]]:
    """Etapa 5. Páginas digitales: capa de texto. Escaneadas: OCR, y su imagen para el LLM.

    Devuelve el texto de cada página y las imágenes como (número de página, JPEG)."""
    scanned = [i for i, p in enumerate(profiles) if p == "scanned"]
    rendered = render_pages(data, scanned)
    pages = []
    for i, text in enumerate(texts):
        if i in rendered:
            ocr_text, score = ocr_image(rendered[i])
            pages.append(PageText(ocr_text, "ocr", reliable=score >= OCR_MIN_SCORE))
        else:
            pages.append(PageText(text))
    return pages, [(i + 1, to_jpeg(rendered[i])) for i in scanned]


def render_document(pages: list[PageText]) -> str:
    """Texto por página con su número y su origen; las páginas sin texto se omiten."""
    return "\n\n".join(
        f"--- Página {n}{' (OCR)' if p.source == 'ocr' else ''} ---\n{p.text.strip()}"
        for n, p in enumerate(pages, 1)
        if p.text.strip()
    )


def extract(
    llm: LLMClient,
    doc_type: str,
    pages: list[PageText],
    images: list[tuple[int, bytes]],
    usage: Usage,
) -> BaseModel:
    """Ruta fast: Gemini sobre la capa de texto. Ruta visual: además, OCR e imágenes."""
    kind = DOC_TYPES[doc_type]
    text = prompt("extract.md").format(label=kind.LABEL, document=render_document(pages))
    if images:
        text += "\n\n" + prompt("visual.md").format(pages=", ".join(str(n) for n, _ in images))
    return generate_structured(llm, text, kind.MODEL, usage, [jpeg for _, jpeg in images])


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
    pages, images = read_pages(data, texts, profiles)
    kind = DOC_TYPES[doc_type]
    usage = Usage()
    doc = extract(llm, doc_type, pages, images, usage)
    return ExtractResponse(
        doc_type=DocTypeResult(value=doc_type, method="forced", confidence="high"),
        route="visual" if images else "fast",
        pages=[PageInfo(page=n, profile=p) for n, p in enumerate(profiles, 1)],
        # sin evidencia, el valor viene de lo que el LLM leyó: el texto o la imagen
        fields=verify_fields(doc, pages, "vision" if images else "text_layer", kind.IDENTIFIERS),
        validations=run_rules(kind.RULES, doc),
        usage=UsageReport(
            **asdict(usage), latency_ms=round((time.perf_counter() - started) * 1000)
        ),
    )
