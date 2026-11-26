from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    # live: Gemini · recorded: solo grabaciones · record: Gemini y graba lo que falte
    llm_mode: Literal["live", "recorded", "record"] = "live"
    recordings_dir: Path = Path("eval/recordings")
    max_file_mb: int = 10
    max_pages: int = 20
    # Clave que /extract exige en el header X-API-Key; vacía: sin autenticación (local)
    api_key: str | None = None
    # Extracciones simultáneas: cada una usa CPU (OCR), memoria y cuota de Gemini
    max_concurrent: int = Field(4, ge=1)
