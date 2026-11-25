from pathlib import Path
from typing import Literal

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
