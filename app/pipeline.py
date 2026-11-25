"""Orquestación del pipeline."""

from collections.abc import Callable, Iterable
from pathlib import Path

from pydantic import BaseModel

from app.doc_types import DOC_TYPES
from app.llm.client import LLMClient, Usage, generate_structured
from app.schemas import Validation

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"


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
