"""Evaluación offline: corre el pipeline completo sobre el dataset sintético y compara
contra el ground truth, por campo y por variante. Escribe eval/report.md.

    python scripts/generate_dataset.py
    LLM_MODE=recorded python eval/run_eval.py --min-clean-accuracy 0.95

Con LLM_MODE=record llama a Gemini solo para lo que no esté grabado (se puede reanudar).
Las grabaciones van por documento y orden de llamada: eval/recordings/<doc>/<variante>/.
"""

import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from statistics import mean
from typing import Any

from app.config import Settings
from app.evidence import flatten
from app.llm.client import LLMClient, LLMError
from app.llm.gemini import GeminiLLM
from app.llm.recorded import RecordedLLM
from app.pipeline import RejectedInput, run

VARIANTS = ("clean", "scanned", "watermark")
RATE_LIMIT_WAIT_S = 60
MAX_MISTAKES = 40


def normalize(value: Any) -> Any:
    """Montos a 2 decimales; texto sin diferencias de espacios ni mayúsculas (sí acentos)."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return round(float(value), 2)
    return " ".join(str(value).split()).casefold()


@dataclass
class Tally:
    docs: int = 0
    errors: int = 0
    classified: int = 0
    expected: int = 0  # campos con valor esperado
    correct: int = 0
    absent: int = 0  # campos que no deben tener valor
    hallucinated: int = 0
    high: int = 0
    high_correct: int = 0
    confidence: Counter = field(default_factory=Counter)
    llm_calls: list[int] = field(default_factory=list)
    input_tokens: list[int] = field(default_factory=list)
    output_tokens: list[int] = field(default_factory=list)
    latency_ms: list[int] = field(default_factory=list)

    def add(self, other: "Tally") -> None:
        for name, value in vars(other).items():
            mine = getattr(self, name)
            if isinstance(mine, Counter):
                mine.update(value)
            elif isinstance(mine, list):
                mine.extend(value)
            else:
                setattr(self, name, mine + value)


@dataclass
class FieldTally:
    expected: int = 0
    correct: int = 0
    absent: int = 0
    hallucinated: int = 0


def field_key(path: str) -> str:
    return re.sub(r"\[\d+\]", "[]", path)


def score(
    doc: str, variant: str, truth: dict, result, tally: Tally, fields: dict, mistakes: list
) -> None:
    """Compara una respuesta con el ground truth y acumula."""
    expected = flatten(truth["fields"])
    got = result.fields if result else {}
    if result:
        tally.classified += result.doc_type.value == truth["doc_type"]
        tally.llm_calls.append(result.usage.llm_calls)
        tally.input_tokens.append(result.usage.input_tokens)
        tally.output_tokens.append(result.usage.output_tokens)
        tally.latency_ms.append(result.usage.latency_ms)
    for path in sorted(expected.keys() | got.keys()):
        want = normalize(expected.get(path))
        found = got.get(path)
        value = normalize(found.value) if found else None
        per_field = fields[(field_key(path), variant)]
        if found and found.value is not None:
            tally.confidence[found.confidence] += 1
        if want is None:
            if path not in expected and value is None:
                continue  # p. ej. "education" vacía en la respuesta: no es un campo real
            tally.absent += 1
            per_field.absent += 1
            if value is not None:
                tally.hallucinated += 1
                per_field.hallucinated += 1
                mistakes.append((doc, variant, path, None, found.value, found.confidence))
            continue
        ok = value == want
        tally.expected += 1
        tally.correct += ok
        per_field.expected += 1
        per_field.correct += ok
        if found and found.confidence == "high":
            tally.high += 1
            tally.high_correct += ok
        if not ok:
            mistakes.append(
                (
                    doc,
                    variant,
                    path,
                    expected[path],
                    found and found.value,
                    found and found.confidence,
                )
            )


def make_llm_for(settings: Settings, live: LLMClient | None, doc: str, variant: str) -> LLMClient:
    if settings.llm_mode == "live":
        return live
    return RecordedLLM(settings.recordings_dir / doc / variant, live, sequential=True)


def extract(settings: Settings, live: LLMClient | None, doc_dir: Path, variant: str):
    """Corre el pipeline; ante límite de cuota espera y reintenta (lo grabado no se repite)."""
    data = (doc_dir / f"{variant}.pdf").read_bytes()
    for attempt in range(3):
        llm = make_llm_for(settings, live, doc_dir.name, variant)
        try:
            return run(data, None, llm, settings), None
        except LLMError as e:
            limited = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)
            if not limited or attempt == 2:
                return None, str(e)
            print(f"  límite de cuota; espero {RATE_LIMIT_WAIT_S} s", flush=True)
            time.sleep(RATE_LIMIT_WAIT_S)
        except RejectedInput as e:
            return None, f"{e.status_code}: {e.detail}"
    return None, "sin respuesta"


def pct(num: float, den: float) -> str:
    return f"{num / den:.1%}" if den else "—"


def as_cell(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str).replace("|", "\\|")


def avg(values: list[int]) -> str:
    return f"{mean(values):,.0f}" if values else "—"


def render_report(
    settings: Settings, tallies: dict[str, Tally], fields: dict, mistakes: list
) -> str:
    total = Tally()
    for t in tallies.values():
        total.add(t)
    rows = [*((v, tallies[v]) for v in VARIANTS if v in tallies), ("**total**", total)]
    lines = [
        "# Reporte de evaluación",
        "",
        f"{date.today().isoformat()} · `LLM_MODE={settings.llm_mode}` · "
        f"`{settings.gemini_model}` · {total.docs} documentos",
        "",
        "## Resumen por variante",
        "",
        "| Variante | Docs | Errores | Clasificación | Exactitud | Alucinación | "
        "Calibración `high` | high / medium / low | Llamadas LLM | Tokens entrada | "
        "Tokens salida | Latencia ms |",
        "|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|",
    ]
    for name, t in rows:
        published = sum(t.confidence.values())
        mix = " / ".join(pct(t.confidence[c], published) for c in ("high", "medium", "low"))
        lines.append(
            f"| {name} | {t.docs} | {t.errors} | {pct(t.classified, t.docs)} | "
            f"{pct(t.correct, t.expected)} | {pct(t.hallucinated, t.absent)} | "
            f"{pct(t.high_correct, t.high)} | {mix} | {avg(t.llm_calls)} | "
            f"{avg(t.input_tokens)} | {avg(t.output_tokens)} | {avg(t.latency_ms)} |"
        )
    lines += [
        "",
        "- **Exactitud:** valor normalizado igual al esperado, sobre los campos que tienen valor.",
        "- **Alucinación:** valor publicado donde el esperado es `null`.",
        "- **Calibración:** exactitud de los valores publicados con `confidence: high`.",
        "- Tokens, llamadas y latencia: promedio por documento. Con `LLM_MODE=recorded` la "
        "latencia no incluye al LLM.",
        "",
        "## Exactitud por campo",
        "",
        "| Campo | " + " | ".join(VARIANTS) + " |",
        "|---|" + "---:|" * len(VARIANTS),
    ]
    keys = sorted({k for k, _ in fields})
    for key in keys:
        cells = [fields.get((key, v)) for v in VARIANTS]
        if not any(c and c.expected for c in cells):
            continue
        lines.append(
            f"| `{key}` | "
            + " | ".join(
                f"{pct(c.correct, c.expected)} ({c.expected})" if c else "—" for c in cells
            )
            + " |"
        )
    absent_keys = [
        k for k in keys if any(fields[(k, v)].absent for v in VARIANTS if (k, v) in fields)
    ]
    if absent_keys:
        lines += [
            "",
            "## Alucinación por campo",
            "",
            "Valores publicados / casos donde el campo no existe en el documento.",
            "",
            "| Campo | " + " | ".join(VARIANTS) + " |",
            "|---|" + "---:|" * len(VARIANTS),
        ]
        for key in absent_keys:
            cells = [fields.get((key, v)) for v in VARIANTS]
            lines.append(
                f"| `{key}` | "
                + " | ".join(f"{c.hallucinated}/{c.absent}" if c else "—" for c in cells)
                + " |"
            )
    lines += [
        "",
        f"## Errores ({len(mistakes)}; se muestran hasta {MAX_MISTAKES})",
        "",
        "| Documento | Variante | Campo | Esperado | Obtenido | Confianza |",
        "|---|---|---|---|---|---|",
    ]
    for doc, variant, path, want, got, conf in mistakes[:MAX_MISTAKES]:
        lines.append(
            f"| {doc} | {variant} | `{path}` | {as_cell(want)} | {as_cell(got)} | {conf or '—'} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluación offline del pipeline")
    parser.add_argument("--dataset", type=Path, default=Path("eval/dataset"))
    parser.add_argument("--out", type=Path, default=Path("eval/report.md"))
    parser.add_argument("--limit", type=int, help="solo los primeros N documentos de cada tipo")
    parser.add_argument("--min-clean-accuracy", type=float, help="falla si clean queda debajo")
    args = parser.parse_args()

    settings = Settings()
    live = None
    if settings.llm_mode in ("live", "record"):
        if not settings.gemini_api_key:
            sys.exit(f"GEMINI_API_KEY es requerida con LLM_MODE={settings.llm_mode}")
        live = GeminiLLM(settings.gemini_api_key, settings.gemini_model)

    docs = sorted(p.parent for p in args.dataset.glob("*/ground_truth.json"))
    if args.limit:
        by_type = defaultdict(list)
        for d in docs:
            by_type[d.name.rsplit("_", 1)[0]].append(d)
        docs = [d for group in by_type.values() for d in group[: args.limit]]
    if not docs:
        sys.exit(f"no hay documentos en {args.dataset}; corre scripts/generate_dataset.py")

    tallies = {v: Tally() for v in VARIANTS}
    fields: dict = defaultdict(FieldTally)
    mistakes: list = []
    for n, doc_dir in enumerate(docs, 1):
        truth = json.loads((doc_dir / "ground_truth.json").read_text(encoding="utf-8"))
        for variant in VARIANTS:
            result, error = extract(settings, live, doc_dir, variant)
            tally = tallies[variant]
            tally.docs += 1
            if error:
                tally.errors += 1
                mistakes.append((doc_dir.name, variant, "(documento)", None, error, None))
            score(doc_dir.name, variant, truth, result, tally, fields, mistakes)
            status = "error" if error else f"{result.route}, {result.usage.llm_calls} llamadas"
            print(f"[{n}/{len(docs)}] {doc_dir.name} {variant}: {status}", flush=True)

    args.out.write_text(render_report(settings, tallies, fields, mistakes), encoding="utf-8")
    clean = tallies["clean"]
    accuracy = clean.correct / clean.expected if clean.expected else 0.0
    print(f"\nreporte: {args.out} · exactitud clean: {accuracy:.1%}")
    if args.min_clean_accuracy is not None and accuracy < args.min_clean_accuracy:
        sys.exit(f"exactitud clean {accuracy:.1%} < mínimo {args.min_clean_accuracy:.1%}")


if __name__ == "__main__":
    main()
