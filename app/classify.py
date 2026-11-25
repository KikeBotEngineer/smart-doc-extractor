"""Etapa 4: clasificación del tipo de documento. Palabras clave; si no hay ganador claro,
una llamada corta al LLM con un enum."""

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.doc_types import DOC_TYPES
from app.evidence import PageText, fold
from app.llm.client import LLMClient, Usage, generate_structured
from app.schemas import DocTypeResult

MIN_HITS = 2  # palabras clave distintas para decidir sin LLM
EXCERPT_CHARS = 3000  # al LLM le basta el inicio del documento
PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "classify.md"


class Classification(BaseModel):
    doc_type: Literal[(*DOC_TYPES, "other")]


def keyword_scores(text: str) -> dict[str, int]:
    """Palabras clave distintas de cada tipo que aparecen como palabra completa."""
    words = set(re.findall(r"\w+", fold(text)))
    return {name: sum(fold(k) in words for k in kind.KEYWORDS) for name, kind in DOC_TYPES.items()}


def classify(llm: LLMClient, pages: list[PageText], usage: Usage) -> DocTypeResult | None:
    """None si el documento no es de ningún tipo soportado."""
    text = "\n".join(p.text for p in pages)
    (best, hits), (_, runner_up) = sorted(
        keyword_scores(text).items(), key=lambda kv: kv[1], reverse=True
    )[:2]
    if hits >= MIN_HITS and hits >= 2 * runner_up:
        return DocTypeResult(value=best, method="keywords", confidence="high")
    options = "\n".join(f"- {name}: {kind.LABEL}" for name, kind in DOC_TYPES.items())
    prompt = PROMPT.read_text(encoding="utf-8").format(
        options=options, document=text[:EXCERPT_CHARS]
    )
    answer = generate_structured(llm, prompt, Classification, usage).doc_type
    if answer == "other":
        return None
    return DocTypeResult(value=answer, method="llm", confidence="medium")
