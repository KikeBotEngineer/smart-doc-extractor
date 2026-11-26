"""Protocolo del cliente LLM y llamada estructurada con validación y un reintento."""

import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, ValidationError

RETRY_WAIT_S = 2  # antes de repetir una llamada fallida: un 429 o un 503 suele ser momentáneo


class LLMError(Exception):
    """El LLM falló o no devolvió una respuesta válida después del reintento.

    `retryable=False`: repetir la llamada no cambia nada (key inválida, petición mal
    formada, grabación faltante)."""

    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True)
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int


class LLMClient(Protocol):
    def generate(
        self, prompt: str, schema: type[BaseModel], images: Sequence[bytes] = ()
    ) -> LLMResponse:
        """Devuelve JSON que debería cumplir `schema`; `images` van en JPEG.

        Lanza LLMError si la llamada falla."""
        ...


@dataclass
class Usage:
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, response: LLMResponse) -> None:
        self.llm_calls += 1
        self.input_tokens += response.input_tokens
        self.output_tokens += response.output_tokens


def generate_structured[M: BaseModel](
    llm: LLMClient, prompt: str, schema: type[M], usage: Usage, images: Sequence[bytes] = ()
) -> M:
    """Llama al LLM y valida con `schema`. Ante error o respuesta inválida, reintenta una vez."""
    retry_prompt = prompt
    for attempt in (1, 2):
        try:
            response = llm.generate(retry_prompt, schema, images)
        except LLMError as e:
            if attempt == 2 or not e.retryable:
                raise
            time.sleep(RETRY_WAIT_S)
            continue
        usage.add(response)
        try:
            return schema.model_validate_json(response.text)
        except ValidationError as e:
            if attempt == 2:
                raise LLMError(f"respuesta inválida tras el reintento: {e}") from e
            retry_prompt = (
                f"{prompt}\n\nTu respuesta anterior no cumplió el esquema:\n{e}\n"
                "Devuelve de nuevo el JSON completo y válido."
            )
    raise AssertionError("inalcanzable")
