"""Implementación real de LLMClient con Gemini y salida estructurada."""

from collections.abc import Sequence

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.llm.client import LLMError, LLMResponse


class GeminiLLM:
    def __init__(self, api_key: str, model: str, client: genai.Client | None = None):
        self._client = client or genai.Client(api_key=api_key)
        self._model = model

    def generate(
        self, prompt: str, schema: type[BaseModel], images: Sequence[bytes] = ()
    ) -> LLMResponse:
        contents = [prompt, *(types.Part.from_bytes(data=i, mime_type="image/png") for i in images)]
        config = types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_json_schema=schema.model_json_schema(),
        )
        try:
            response = self._client.models.generate_content(
                model=self._model, contents=contents, config=config
            )
        except Exception as e:  # red, cuota, 5xx: todo es "Gemini falló"
            raise LLMError(f"Gemini falló: {e}") from e
        meta = response.usage_metadata
        return LLMResponse(
            text=response.text or "",
            input_tokens=(meta and meta.prompt_token_count) or 0,
            # los tokens de razonamiento se cobran como salida
            output_tokens=((meta and meta.candidates_token_count) or 0)
            + ((meta and meta.thoughts_token_count) or 0),
        )
