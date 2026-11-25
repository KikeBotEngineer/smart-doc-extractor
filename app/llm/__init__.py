from app.config import Settings
from app.llm.client import LLMClient
from app.llm.gemini import GeminiLLM
from app.llm.recorded import RecordedLLM


def make_llm(settings: Settings) -> LLMClient:
    if settings.llm_mode == "recorded":
        return RecordedLLM(settings.recordings_dir)
    if not settings.gemini_api_key:
        raise RuntimeError(f"GEMINI_API_KEY es requerida con LLM_MODE={settings.llm_mode}")
    live = GeminiLLM(settings.gemini_api_key, settings.gemini_model)
    return RecordedLLM(settings.recordings_dir, live) if settings.llm_mode == "record" else live
