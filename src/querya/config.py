from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"

DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-opus-5-5",
    "openai": "qwen2.5-coder:3b",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="QUERYA_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = f"sqlite:///{(DEFAULT_DATA_DIR / 'retail.db').as_posix()}"
    trace_database_url: str = f"sqlite:///{(DEFAULT_DATA_DIR / 'traces.db').as_posix()}"

    llm_provider: Literal["openai", "anthropic"] = "openai"
    llm_model: str | None = None
    llm_max_tokens: int = Field(default=4096, ge=256)
    llm_timeout_s: float = Field(default=120.0, gt=0)
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    openai_base_url: str = "http://localhost:11434/v1"
    openai_api_key: SecretStr = SecretStr("ollama")
    # Falls back to ANTHROPIC_API_KEY (read by the SDK) when unset.
    anthropic_api_key: SecretStr | None = None
    anthropic_show_thinking: bool = True
    glossary_path: Path | None = None

    max_rows: int = Field(default=200, ge=1, le=10_000)
    statement_timeout_ms: int = Field(default=5_000, ge=100)
    max_sql_retries: int = Field(default=3, ge=0, le=10)
    max_steps: int = Field(default=12, ge=2, le=50)

    langfuse_enabled: bool = False
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    log_level: str = "INFO"

    @property
    def model_name(self) -> str:
        return self.llm_model or DEFAULT_MODELS[self.llm_provider]


@lru_cache
def get_settings() -> Settings:
    return Settings()
