"""Etapa 6: verificación de evidencia por tipo de campo.

La búsqueda solo confirma o descarta un valor propuesto; nunca genera valores.
"""

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from pydantic import BaseModel
from rapidfuzz import fuzz

from app.schemas import Evidence, FieldResult, Source

FUZZY_MIN = 80  # cobertura mínima para texto libre
SNIPPET_PAD = 40  # caracteres de contexto a cada lado

Span = tuple[int, int]


@dataclass(frozen=True)
class PageText:
    """Texto de una página y de dónde salió. `reliable=False`: OCR con baja confianza."""

    text: str
    source: Source = "text_layer"
    reliable: bool = True


Patterns = list[tuple[re.Pattern, Callable[[tuple], set]]]

NUMBER = re.compile(r"\d[\d.,]*\d|\d")
YEAR_MONTH = re.compile(r"\d{4}-\d{2}")
MONTHS = {
    "ene": 1, "jan": 1, "feb": 2, "mar": 3, "abr": 4, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "aug": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12, "dec": 12,
}  # fmt: skip
MONTH = r"([a-záéíóú]{3,10})\.?"


def _month(name: str) -> int | None:
    return MONTHS.get(name[:3].lower())


# Cada patrón da las lecturas posibles (año, mes[, día]) de lo que encontró.
DATE_PATTERNS: Patterns = [
    (re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})"), lambda g: {(int(g[0]), int(g[1]), int(g[2]))}),
    (  # 22/06/2023 o 06/22/2023
        re.compile(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})"),
        lambda g: {(int(g[2]), int(g[1]), int(g[0])), (int(g[2]), int(g[0]), int(g[1]))},
    ),
    (  # 22 de junio de 2023, 22 jun 2023
        re.compile(rf"(\d{{1,2}})\s*(?:de\s*)?{MONTH}\s*(?:del?\s*)?(\d{{4}})", re.I),
        lambda g: {(int(g[2]), _month(g[1]), int(g[0]))},
    ),
    (  # June 22, 2023
        re.compile(rf"{MONTH}\s+(\d{{1,2}}),?\s+(\d{{4}})", re.I),
        lambda g: {(int(g[2]), _month(g[0]), int(g[1]))},
    ),
]
YEAR_MONTH_PATTERNS: Patterns = [
    (re.compile(r"(\d{4})-(\d{1,2})\b"), lambda g: {(int(g[0]), int(g[1]))}),
    (re.compile(r"\b(\d{1,2})[/.-](\d{4})"), lambda g: {(int(g[1]), int(g[0]))}),
    (re.compile(rf"{MONTH}\s*(?:del?\s*)?(\d{{4}})", re.I), lambda g: {(int(g[1]), _month(g[0]))}),
]


def parse_number(token: str) -> float | None:
    """`1,160.00`, `1.160,00`, `1160` → 1160.0. None si es ambiguo (p. ej. un teléfono)."""
    if "," in token and "." in token:
        dec = max(token.rfind(","), token.rfind("."))
        return float(re.sub(r"[.,]", "", token[:dec]) + "." + token[dec + 1 :])
    sep = "," if "," in token else "." if "." in token else None
    if sep is None:
        return float(token)
    parts = token.split(sep)
    if len(parts) == 2 and len(parts[1]) != 3:
        return float(f"{parts[0]}.{parts[1]}")
    if all(len(p) == 3 for p in parts[1:]):
        return float("".join(parts))
    return None


def _find_patterns(patterns: Patterns, target: tuple, page: str) -> Span | None:
    for regex, readings in patterns:
        for m in regex.finditer(page):
            if target in readings(m.groups()):
                return m.span()
    return None


def find_number(value: float, page: str) -> Span | None:
    # ponytail: un número corto (cantidad 2) coincide con cualquier "2" de la página;
    # acotar a la zona del campo si la calibración lo pide.
    for m in NUMBER.finditer(page):
        n = parse_number(m.group())
        if n is not None and abs(n - value) < 0.005:
            return m.span()
    return None


def find_date(value: date, page: str) -> Span | None:
    return _find_patterns(DATE_PATTERNS, (value.year, value.month, value.day), page)


def find_year_month(value: str, page: str) -> Span | None:
    year, month = value.split("-")
    return _find_patterns(YEAR_MONTH_PATTERNS, (int(year), int(month)), page)


def find_literal(value: str, page: str) -> Span | None:
    """Coincidencia literal sin importar mayúsculas ni espacios: el OCR suele perderlos
    ("Licencia desoftware anual") sin cambiar el contenido."""
    needle = r"\s*".join(re.escape(c) for c in value if not c.isspace())
    m = re.search(rf"(?<!\w){needle}(?!\w)", page, re.I)
    return m.span() if m else None


def fold(text: str) -> str:
    """Minúsculas y sin acentos, carácter por carácter: conserva las posiciones."""
    return "".join(unicodedata.normalize("NFD", c)[0].lower()[0] for c in text)


def snippet(page: str, start: int, end: int) -> str:
    """El fragmento encontrado con contexto, cortado en límites de palabra."""
    a = page.rfind(" ", 0, max(0, start - SNIPPET_PAD)) + 1
    b = page.find(" ", min(len(page), end + SNIPPET_PAD))
    return page[a : len(page) if b == -1 else b]


def find_evidence(value: Any, identifier: bool, pages: list[str]) -> tuple[int, str, bool] | None:
    """(página, snippet, literal) de la primera coincidencia, o None."""
    if isinstance(value, int | float):
        finder = find_number
    elif isinstance(value, date):
        finder = find_date
    elif YEAR_MONTH.fullmatch(value):
        finder = find_year_month
    else:
        finder = find_literal
    for n, page in enumerate(pages, 1):
        if span := finder(value, page):
            return n, snippet(page, *span), True
    if finder is find_literal and not identifier:  # texto libre: cobertura difusa
        for n, page in enumerate(pages, 1):
            hit = fuzz.partial_ratio_alignment(fold(value), fold(page), score_cutoff=FUZZY_MIN)
            if hit:
                return n, snippet(page, hit.dest_start, hit.dest_end), False
    return None


def flatten(data: dict[str, Any]) -> dict[str, Any]:
    """{'line_items': [{'amount': 1}]} → {'line_items[0].amount': 1}. Lista vacía → None."""
    out: dict[str, Any] = {}
    for name, value in data.items():
        if not isinstance(value, list):
            out[name] = value
        elif not value:
            out[name] = None
        else:
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    out.update({f"{name}[{i}].{k}": v for k, v in item.items()})
                else:
                    out[f"{name}[{i}]"] = item
    return out


def verify_value(
    path: str, value: Any, pages: list[PageText], fallback_source: Source, identifiers: set[str]
) -> FieldResult:
    """Sin evidencia, el valor queda con confianza baja y `fallback_source` (de dónde lo
    leyó el LLM)."""
    if value is None:
        return FieldResult(missing_reason="not_present")
    leaf = re.sub(r"\[\d+\]$", "", path.rsplit(".", 1)[-1])
    found = find_evidence(value, leaf in identifiers, [" ".join(p.text.split()) for p in pages])
    if found is None:
        return FieldResult(value=value, confidence="low", source=fallback_source)
    n, text, literal = found
    page = pages[n - 1]
    return FieldResult(
        value=value,
        confidence="high" if literal and page.reliable else "medium",
        source=page.source,
        evidence=Evidence(page=n, snippet=text),
    )


def verify_fields(
    doc: BaseModel, pages: list[PageText], fallback_source: Source, identifiers: set[str]
) -> dict[str, FieldResult]:
    """Un FieldResult por campo hoja."""
    return {
        path: verify_value(path, value, pages, fallback_source, identifiers)
        for path, value in flatten(doc.model_dump()).items()
    }
