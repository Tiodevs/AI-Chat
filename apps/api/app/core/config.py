from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = ".env" if Path(".env").is_file() else None


def rewrite_database_url(value: str) -> str:
    """Troca postgresql:// por postgresql+asyncpg://. Seção 17 do SDD."""
    prefix = "postgresql://"
    if value.startswith(prefix):
        return "postgresql+asyncpg://" + value.removeprefix(prefix)
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["local", "test", "development", "production"] = "local"
    database_url: str = ""
    gemini_api_key: str = ""
    chat_model: str = "gemini-2.5-flash"
    embedding_model: str = "gemini-embedding-2"
    embedding_dimensions: int = 768
    app_ai_adapter: Literal["gemini", "fake"] = "gemini"
    web_origin: str = "http://localhost:5173"
    admin_email: str = ""
    admin_password: str = ""
    retrieval_min_similarity: float = 0.50
    llm_daily_token_budget: int = 0
    metrics_token: str = ""
    rate_limit_hmac_key: str = ""
    pseudonym_key: str = ""
    privacy_contact_email: str = ""
    log_level: str = "INFO"
    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "atrium-dev"
    langsmith_endpoint: str = ""
    langsmith_workspace_id: str = ""
    langsmith_tracing_sampling_rate: float = 1.0

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: object) -> object:
        if isinstance(value, str):
            return rewrite_database_url(value)
        return value
