from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = ".env" if Path(".env").is_file() else None
CLOUD_ENVIRONMENTS = frozenset({"development", "production"})


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
    app_ai_adapter: Literal["gemini", "fake", "demo"] = "gemini"
    web_origin: str = "http://localhost:5173"
    admin_email: str = ""
    admin_password: str = ""
    retrieval_min_similarity: float = 0.50
    llm_daily_token_budget: int = 0
    metrics_token: str = ""
    rate_limit_hmac_key: str = ""
    pseudonym_key: str = ""
    edge_secret: str = ""
    privacy_contact_email: str = ""
    log_level: str = "INFO"
    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "atrium-dev"
    langsmith_endpoint: str = ""
    langsmith_workspace_id: str = ""
    langsmith_tracing_sampling_rate: float = 1.0
    langsmith_run_url_template: str = ""

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: object) -> object:
        if isinstance(value, str):
            return rewrite_database_url(value)
        return value

    @model_validator(mode="after")
    def _demo_only_off_the_cloud(self) -> "Settings":
        """O modo `demo` responde por regras. Ele não pode chegar a um ambiente da Railway."""
        if self.app_ai_adapter == "demo" and self.app_env in CLOUD_ENVIRONMENTS:
            raise ValueError("APP_AI_ADAPTER=demo só vale com APP_ENV local ou test.")
        return self


class MissingSafeguards(RuntimeError):
    """A API não sobe na Railway sem o teto de tokens e as chaves de HMAC."""

    def __init__(self, app_env: str, variables: list[str]) -> None:
        super().__init__(
            f"APP_ENV={app_env} exige {', '.join(variables)}. "
            "LLM_DAILY_TOKEN_BUDGET precisa ser maior que zero, e as chaves não podem ficar "
            "vazias. Zero e vazio só valem com APP_ENV local ou test."
        )
        self.variables = tuple(variables)


def missing_safeguards(settings: Settings) -> list[str]:
    """Variáveis sem valor seguro para a API num ambiente da Railway. Seções 7.1 e 10.4 do SDD.

    O teto de tokens é a proteção de custo que os limites por IP não dão. A regra vale para a
    API, não para todo `Settings`: o `retention-job` lê a mesma configuração sem essas variáveis.
    """
    if settings.app_env not in CLOUD_ENVIRONMENTS:
        return []
    missing: list[str] = []
    if settings.llm_daily_token_budget <= 0:
        missing.append("LLM_DAILY_TOKEN_BUDGET")
    if not settings.rate_limit_hmac_key.strip():
        missing.append("RATE_LIMIT_HMAC_KEY")
    if not settings.pseudonym_key.strip():
        missing.append("PSEUDONYM_KEY")
    return missing


def require_safeguards(settings: Settings) -> None:
    missing = missing_safeguards(settings)
    if missing:
        raise MissingSafeguards(settings.app_env, missing)


def edge_guard_secret(settings: Settings) -> str:
    """O segredo que a API exige em /v1. Seção 10.3 do SDD.

    Só vale em `development` e `production`: em `local` e `test`, o Vite faz o proxy sem o
    cabeçalho da Vercel. Vazio deixa o portão aberto.
    """
    if settings.app_env not in CLOUD_ENVIRONMENTS:
        return ""
    return settings.edge_secret.strip()
