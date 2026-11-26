"""Orquestación del pipeline."""

import json
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import asdict
from io import BytesIO
from pathlib import Path
from types import ModuleType
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from pypdf import PasswordType, PdfReader

from app.classify import classify
from app.config import Settings
from app.doc_types import DOC_TYPES
from app.evidence import PageText, verify_fields
from app.llm.client import LLMClient, LLMError, Usage, generate_structured
from app.pdf.ocr import ocr_image, render_page, to_jpeg
from app.pdf.profile import PageProfile, profile_pages
from app.pdf.text_layer import page_texts
from app.schemas import (
    DocTypeResult,
    ExtractResponse,
    FieldResult,
    PageInfo,
    Source,
    UsageReport,
    Validation,
)

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

    Devuelve el texto de cada página y las imágenes como (número de página, JPEG).
    Una página renderizada a la vez: en memoria solo queda su JPEG."""
    pages, images = [], []
    for i, (text, profile) in enumerate(zip(texts, profiles, strict=True)):
        if profile != "scanned":
            pages.append(PageText(text))
            continue
        image = render_page(data, i)
        ocr_text, score = ocr_image(image)
        pages.append(PageText(ocr_text, "ocr", reliable=score >= OCR_MIN_SCORE))
        images.append((i + 1, to_jpeg(image)))
    return pages, images


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
    text = build_prompt("extract.md", kind, pages, images)
    return generate_structured(llm, text, kind.MODEL, usage, [jpeg for _, jpeg in images])


def build_prompt(
    template: str, kind: ModuleType, pages: list[PageText], images: list, **values: str
) -> str:
    text = prompt(template).format(label=kind.LABEL, document=render_document(pages), **values)
    if images:
        text += "\n\n" + prompt("visual.md").format(pages=", ".join(str(n) for n, _ in images))
    return text


class RecoveredField(BaseModel):
    field: str = Field(description="Nombre del campo, tal como se pidió")
    value: str | None = Field(description="Valor tal como aparece en el documento, o null")


class Recovery(BaseModel):
    fields: list[RecoveredField]


def recover(
    llm: LLMClient,
    kind: ModuleType,
    doc: BaseModel,
    fields: dict[str, FieldResult],
    pages: list[PageText],
    images: list[tuple[int, bytes]],
    fallback: Source,
    usage: Usage,
) -> tuple[BaseModel, dict[str, FieldResult]]:
    """Etapa 7: una sola llamada más, solo con los campos sin evidencia.

    Valor nuevo con evidencia confiable: se acepta. null: `insufficient_evidence`. Otro
    valor sin evidencia confiable: `conflicting_candidates`. El mismo valor: sigue `low`.
    Si la llamada falla, se queda el resultado de la primera pasada."""
    pending = {path: f.value for path, f in fields.items() if f.confidence == "low"}
    if not pending:
        return doc, fields
    # ponytail: el contexto es el documento completo; acotarlo a la página del campo si el
    # costo en documentos largos lo pide.
    data = doc.model_dump()
    listing = "\n".join(
        f"- {path}: {as_json(value)}{item_context(data, path)}" for path, value in pending.items()
    )
    text = build_prompt("recover.md", kind, pages, images, fields=listing)
    try:
        response = llm.generate(text, Recovery, [jpeg for _, jpeg in images])
        usage.add(response)
        answers = Recovery.model_validate_json(response.text).fields
    except (LLMError, ValidationError):
        return doc, fields
    fields = dict(fields)
    for answer in answers:
        if answer.field not in pending:
            continue
        path = answer.field
        if answer.value is None:
            doc = with_field(kind.MODEL, doc, path, None) or doc
            fields[path] = FieldResult(missing_reason="insufficient_evidence")
            continue
        candidate = with_field(kind.MODEL, doc, path, answer.value)
        if candidate is None:  # el valor no tiene el tipo del campo
            continue
        value = get_field(candidate.model_dump(), path)
        # con las anclas de su partida: un "2" de otro renglón no cuenta
        result = verify_fields(candidate, pages, fallback, kind.IDENTIFIERS)[path]
        # un número o fecha en "medium" puede venir de otro renglón: no basta
        trusted = result.confidence == "high" or (
            result.confidence == "medium" and isinstance(value, str)
        )
        if trusted:
            doc, fields[path] = candidate, result
        elif value != pending[path]:
            doc = with_field(kind.MODEL, doc, path, None) or doc
            fields[path] = FieldResult(missing_reason="conflicting_candidates")
    return doc, fields


def as_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def item_context(data: dict, path: str) -> str:
    """Los otros valores de la partida, para que el LLM ubique el renglón correcto."""
    if "." not in path:
        return ""
    item, leaf = path.rsplit(".", 1)
    others = {k: v for k, v in get_field(data, item).items() if k != leaf and v is not None}
    return f" (misma partida: {as_json(others)})" if others else ""


def _keys(path: str) -> list[str | int]:
    """'line_items[1].amount' → ['line_items', 1, 'amount']"""
    return [int(k) if k.isdigit() else k for k in re.findall(r"[^.\[\]]+", path)]


def get_field(data: Any, path: str) -> Any:
    for key in _keys(path):
        data = data[key]
    return data


def with_field[M: BaseModel](model: type[M], doc: BaseModel, path: str, value: Any) -> M | None:
    """Copia de `doc` con el campo cambiado, o None si el valor no es válido para el modelo."""
    data = doc.model_dump()
    *parents, last = _keys(path)
    target = data
    for key in parents:
        target = target[key]
    target[last] = value
    try:
        return model.model_validate(data)
    except ValidationError:
        return None


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
    texts = page_texts(data)
    profiles = profile_pages(data, texts)
    if all(p == "empty" for p in profiles):
        raise RejectedInput(422, "el PDF no tiene contenido")
    pages, images = read_pages(data, texts, profiles)
    usage = Usage()
    # se clasifica después de leer las páginas: un escaneo solo tiene texto vía OCR
    if doc_type:
        detected = DocTypeResult(value=doc_type, method="forced", confidence="high")
    elif (detected := classify(llm, pages, usage)) is None:
        raise RejectedInput(422, "el documento no es de ningún tipo soportado")
    kind = DOC_TYPES[detected.value]
    doc = extract(llm, detected.value, pages, images, usage)
    # sin evidencia, el valor viene de lo que el LLM leyó: el texto o la imagen
    fallback: Source = "vision" if images else "text_layer"
    fields = verify_fields(doc, pages, fallback, kind.IDENTIFIERS)
    doc, fields = recover(llm, kind, doc, fields, pages, images, fallback, usage)
    return ExtractResponse(
        doc_type=detected,
        route="visual" if images else "fast",
        pages=[PageInfo(page=n, profile=p) for n, p in enumerate(profiles, 1)],
        fields=fields,
        validations=run_rules(kind.RULES, doc),
        usage=UsageReport(
            **asdict(usage), latency_ms=round((time.perf_counter() - started) * 1000)
        ),
    )
