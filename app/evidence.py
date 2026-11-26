"""Etapa 6: verificación de evidencia por tipo de campo.

La búsqueda solo confirma o descarta un valor propuesto; nunca genera valores.
"""

import math
import re
import unicodedata
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date
from typing import Any

from pydantic import BaseModel
from rapidfuzz import fuzz

from app.schemas import Evidence, FieldResult, Source

FUZZY_MIN = 80  # cobertura mínima para texto libre
SNIPPET_PAD = 40  # caracteres de contexto a cada lado
ROW_SLACK = 10  # caracteres alrededor de las anclas de una partida que aún son su renglón

Span = tuple[int, int]
Match = tuple[int, Span, bool]  # (página, posición, literal)


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


def _find_patterns(patterns: Patterns, target: tuple, page: str) -> Iterator[Span]:
    for regex, readings in patterns:
        for m in regex.finditer(page):
            if target in readings(m.groups()):
                yield m.span()


def find_number(value: float, page: str) -> Iterator[Span]:
    for m in NUMBER.finditer(page):
        n = parse_number(m.group())
        if n is not None and abs(n - value) < 0.005:
            yield m.span()


def find_date(value: date, page: str) -> Iterator[Span]:
    return _find_patterns(DATE_PATTERNS, (value.year, value.month, value.day), page)


def find_year_month(value: str, page: str) -> Iterator[Span]:
    year, month = value.split("-")
    return _find_patterns(YEAR_MONTH_PATTERNS, (int(year), int(month)), page)


def find_literal(value: str, page: str) -> Iterator[Span]:
    """Coincidencia literal sin importar mayúsculas ni espacios: el OCR suele perderlos
    ("Licencia desoftware anual") sin cambiar el contenido."""
    needle = r"\s*".join(re.escape(c) for c in value if not c.isspace())
    return (m.span() for m in re.finditer(rf"(?<!\w){needle}(?!\w)", page, re.I))


def fold(text: str) -> str:
    """Minúsculas y sin acentos, carácter por carácter: conserva las posiciones."""
    return "".join(unicodedata.normalize("NFD", c)[0].lower()[0] for c in text)


def snippet(page: str, start: int, end: int) -> str:
    """El fragmento encontrado con contexto, cortado en límites de palabra."""
    a = page.rfind(" ", 0, max(0, start - SNIPPET_PAD)) + 1
    b = page.find(" ", min(len(page), end + SNIPPET_PAD))
    return page[a : len(page) if b == -1 else b]


def find_matches(value: Any, identifier: bool, pages: list[str]) -> list[Match]:
    """Todas las coincidencias literales, en orden. Si no hay y es texto libre, la mejor
    coincidencia difusa."""
    if isinstance(value, int | float):
        finder = find_number
    elif isinstance(value, date):
        finder = find_date
    elif YEAR_MONTH.fullmatch(value):
        finder = find_year_month
    else:
        finder = find_literal
    found = sorted({(n, span) for n, page in enumerate(pages, 1) for span in finder(value, page)})
    if found:
        return [(n, span, True) for n, span in found]
    if finder is find_literal and not identifier:  # texto libre: cobertura difusa
        for n, page in enumerate(pages, 1):
            hit = fuzz.partial_ratio_alignment(fold(value), fold(page), score_cutoff=FUZZY_MIN)
            if hit:
                return [(n, (hit.dest_start, hit.dest_end), False)]
    return []


def find_evidence(value: Any, identifier: bool, pages: list[str]) -> tuple[int, str, bool] | None:
    """(página, snippet, literal) de la primera coincidencia, o None."""
    if not (found := find_matches(value, identifier, pages)):
        return None
    n, span, literal = found[0]
    return n, snippet(pages[n - 1], *span), literal


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


def _collapse(pages: list[PageText]) -> list[str]:
    return [" ".join(p.text.split()) for p in pages]


def _matches(path: str, value: Any, texts: list[str], identifiers: set[str]) -> list[Match]:
    leaf = re.sub(r"\[\d+\]$", "", path.rsplit(".", 1)[-1])
    return find_matches(value, leaf in identifiers, texts)


def _result(
    value: Any, match: Match, pages: list[PageText], texts: list[str], certain: bool = True
) -> FieldResult:
    n, span, literal = match
    page = pages[n - 1]
    return FieldResult(
        value=value,
        confidence="high" if literal and page.reliable and certain else "medium",
        source=page.source,
        evidence=Evidence(page=n, snippet=snippet(texts[n - 1], *span)),
    )


def verify_value(
    path: str, value: Any, pages: list[PageText], fallback_source: Source, identifiers: set[str]
) -> FieldResult:
    """Un solo campo, sin el contexto de su partida. Sin evidencia, el valor queda con
    confianza baja y `fallback_source` (de dónde lo leyó el LLM)."""
    if value is None:
        return FieldResult(missing_reason="not_present")
    texts = _collapse(pages)
    if not (found := _matches(path, value, texts, identifiers)):
        return FieldResult(value=value, confidence="low", source=fallback_source)
    return _result(value, found[0], pages, texts)


def _place(matches: list[Match], anchors: list[Match]) -> tuple[Match, bool]:
    """La coincidencia dentro del tramo que cubren las anclas de la partida (o la más
    cercana a él), y si quedó dentro. Sin anclas, solo es segura si es única."""
    if not anchors:
        return matches[0], len(matches) == 1

    def gap(match: Match) -> float:
        same_page = [a[1] for a in anchors if a[0] == match[0]]
        if not same_page:
            return math.inf
        start = min(s for s, _ in same_page) - ROW_SLACK
        end = max(e for _, e in same_page) + ROW_SLACK
        return max(start - match[1][1], match[1][0] - end, 0)  # distancia entre tramos

    best = min(matches, key=gap)
    return best, gap(best) == 0


def verify_fields(
    doc: BaseModel, pages: list[PageText], fallback_source: Source, identifiers: set[str]
) -> dict[str, FieldResult]:
    """Un FieldResult por campo hoja.

    En una partida, la evidencia de cada campo debe caer en el tramo de texto que cubren
    sus anclas: los otros campos de la partida que aparecen una sola vez. Así la cantidad 4
    de la partida 5 no toma como evidencia el 4 de la partida 2. Fuera de ese tramo, la
    evidencia es parcial."""
    texts = _collapse(pages)
    flat = flatten(doc.model_dump())
    found = {p: _matches(p, v, texts, identifiers) for p, v in flat.items() if v is not None}
    results = {}
    for path, value in flat.items():
        if value is None:
            results[path] = FieldResult(missing_reason="not_present")
            continue
        matches = found[path]
        if not matches:
            results[path] = FieldResult(value=value, confidence="low", source=fallback_source)
            continue
        item = path.rsplit(".", 1)[0] if "." in path else None  # "line_items[4]"
        if item is None:
            results[path] = _result(value, matches[0], pages, texts)
            continue
        anchors = [
            m
            for other, ms in found.items()
            if other != path and other.startswith(f"{item}.") and len(ms) == 1
            for m in ms
        ]
        match, certain = _place(matches, anchors)
        results[path] = _result(value, match, pages, texts, certain)
    return results
