from app.config import Settings
from app.llm.client import LLMClient
from app.llm.gemini import GeminiLLM
from app.llm.recorded import RecordedLLM


def make_llm(settings: Settings) -> LLMClient:
    """Cliente de la API. `record` es solo para la evaluación (eval/run_eval.py): en la API
    guardaría en disco lo extraído de cada documento."""
    if settings.llm_mode == "record":
        raise RuntimeError(
            "LLM_MODE=record es solo para eval/run_eval.py; la API usa live o recorded"
        )
    if settings.llm_mode == "recorded":
        return RecordedLLM(settings.recordings_dir)
    if not settings.gemini_api_key:
        raise RuntimeError(f"GEMINI_API_KEY es requerida con LLM_MODE={settings.llm_mode}")
    return GeminiLLM(settings.gemini_api_key, settings.gemini_model)
