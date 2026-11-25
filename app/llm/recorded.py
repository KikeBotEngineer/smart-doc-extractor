"""Respuestas grabadas: tests y CI sin red ni costo."""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from pydantic import BaseModel

from app.llm.client import LLMClient, LLMError, LLMResponse


def recording_key(prompt: str, schema: type[BaseModel], images: Sequence[bytes]) -> str:
    """Cambia si cambia el prompt, el esquema o las imágenes: hay que regrabar."""
    # ponytail: el hash de las imágenes depende del render; si difiere entre plataformas,
    # usar hash del PDF + número de página.
    payload = json.dumps(
        [schema.model_json_schema(), prompt, [hashlib.sha256(i).hexdigest() for i in images]],
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class RecordedLLM:
    """Reproduce respuestas guardadas en `directory`. Con `live`, graba las que falten."""

    def __init__(self, directory: Path, live: LLMClient | None = None):
        self.directory = directory
        self.live = live

    def generate(
        self, prompt: str, schema: type[BaseModel], images: Sequence[bytes] = ()
    ) -> LLMResponse:
        path = self.directory / f"{recording_key(prompt, schema, images)}.json"
        if path.exists():
            return LLMResponse(**json.loads(path.read_text(encoding="utf-8")))
        if self.live is None:
            raise LLMError(f"sin grabación {path.name}; regrabar con LLM_MODE=record")
        response = self.live.generate(prompt, schema, images)
        self.directory.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(response), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return response
