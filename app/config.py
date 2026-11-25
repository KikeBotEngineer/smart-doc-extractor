from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    llm_mode: Literal["live", "recorded"] = "live"
