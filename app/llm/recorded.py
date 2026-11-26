"""Respuestas grabadas: tests y CI sin red ni costo."""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from pydantic import BaseModel

from app.llm.client import LLMClient, LLMError, LLMResponse

PROMPTS = Path(__file__).resolve().parents[2] / "prompts"


def _sha(payload: object) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def recording_key(prompt: str, schema: type[BaseModel], images: Sequence[bytes]) -> str:
    """Cambia si cambia el prompt, el esquema o las imágenes: hay que regrabar."""
    images_sha = [hashlib.sha256(i).hexdigest() for i in images]
    return _sha([schema.model_json_schema(), prompt, images_sha])


def fingerprint(schema: type[BaseModel]) -> str:
    """Esquema y plantillas de prompts, sin el documento: estable entre plataformas."""
    templates = {p.name: p.read_text(encoding="utf-8") for p in sorted(PROMPTS.glob("*.md"))}
    return _sha([schema.model_json_schema(), templates])


class RecordedLLM:
    """Reproduce respuestas guardadas en `directory`. Con `live`, graba las que falten.

    Por defecto la clave es el hash del prompt y las imágenes. Con `sequential`, la clave
    es el orden de la llamada (00.json, 01.json...) y cada grabación guarda una huella del
    esquema y las plantillas: sirve cuando el OCR o el render pueden variar entre
    plataformas, como en la evaluación (un directorio por documento)."""

    def __init__(self, directory: Path, live: LLMClient | None = None, sequential: bool = False):
        self.directory = directory
        self.live = live
        self.sequential = sequential
        self.calls = 0

    def generate(
        self, prompt: str, schema: type[BaseModel], images: Sequence[bytes] = ()
    ) -> LLMResponse:
        if self.sequential:
            path = self.directory / f"{self.calls:02d}.json"
            expected = fingerprint(schema)
        else:
            path = self.directory / f"{recording_key(prompt, schema, images)}.json"
            expected = None
        self.calls += 1
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.pop("fingerprint", None) == expected:
                return LLMResponse(**data)
            if self.live is None:
                raise LLMError(f"grabación obsoleta {path}; regrabar con LLM_MODE=record")
        elif self.live is None:
            raise LLMError(f"sin grabación {path}; regrabar con LLM_MODE=record")
        response = self.live.generate(prompt, schema, images)
        self.directory.mkdir(parents=True, exist_ok=True)
        record = asdict(response) | ({"fingerprint": expected} if expected else {})
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return response
