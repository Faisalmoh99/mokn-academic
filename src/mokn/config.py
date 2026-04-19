"""Central settings, loaded from environment (.env) via pydantic-settings.

One Settings instance per process. Import `get_settings()` — never instantiate
Settings directly elsewhere, so env overrides stay predictable in tests.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["dev", "prod", "test"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    gemini_api_key: str = Field(..., description="Google AI Studio API key.")
    chroma_persist_dir: str = Field(
        default="./data/chroma",
        description="Local directory Chroma writes collections into.",
    )
    embedding_model: str = Field(
        default="paraphrase-multilingual-MiniLM-L12-v2",
        description="Sentence-transformers model id (must support Arabic).",
    )
    log_level: LogLevel = "INFO"
    env: Environment = "dev"

    llm_log_dir: str = Field(
        default="./logs/llm",
        description="Where GeminiClient persists prompt+response JSONL for debugging.",
    )
    default_model_name: str = Field(
        default="gemini-flash-latest",
        description="Gemini model id used unless overridden per-call.",
    )

    @property
    def chroma_path(self) -> Path:
        return Path(self.chroma_persist_dir).expanduser().resolve()

    @property
    def llm_log_path(self) -> Path:
        return Path(self.llm_log_dir).expanduser().resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


def configure_logging(settings: Settings | None = None) -> None:
    """Idempotent root logger setup. Call once in main.py / script entrypoints."""
    s = settings or get_settings()
    logging.basicConfig(
        level=getattr(logging, s.log_level),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )
