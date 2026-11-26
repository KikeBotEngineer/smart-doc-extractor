"""Implementación real de LLMClient con Gemini y salida estructurada."""

from collections.abc import Sequence

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from app.llm.client import LLMError, LLMResponse

# Una llamada con 20 imágenes y razonamiento puede tardar ~1 min; sin tope, una llamada
# colgada retiene un hilo y un lugar de MAX_CONCURRENT para siempre.
TIMEOUT_S = 90


class GeminiLLM:
    def __init__(self, api_key: str, model: str, client: genai.Client | None = None):
        # google-genai 3.x usa v1 por defecto, que no soporta salida estructurada
        self._client = client or genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(api_version="v1beta", timeout=TIMEOUT_S * 1000),
        )
        self._model = model

    def generate(
        self, prompt: str, schema: type[BaseModel], images: Sequence[bytes] = ()
    ) -> LLMResponse:
        parts = [types.Part.from_bytes(data=jpeg, mime_type="image/jpeg") for jpeg in images]
        contents = [prompt, *parts]
        config = types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_json_schema=schema.model_json_schema(),
        )
        try:
            response = self._client.models.generate_content(
                model=self._model, contents=contents, config=config
            )
        except errors.ClientError as e:  # 4xx: key, permisos o petición; salvo 408 y 429
            raise LLMError(f"Gemini falló: {e}", retryable=e.code in (408, 429)) from e
        except Exception as e:  # red, timeout, 5xx: puede pasar al reintentar
            raise LLMError(f"Gemini falló: {e}") from e
        meta = response.usage_metadata
        return LLMResponse(
            text=response.text or "",
            input_tokens=(meta and meta.prompt_token_count) or 0,
            # los tokens de razonamiento se cobran como salida
            output_tokens=((meta and meta.candidates_token_count) or 0)
            + ((meta and meta.thoughts_token_count) or 0),
        )
