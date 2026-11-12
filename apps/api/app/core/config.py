"""Configuração da API, lida do ambiente e do `.env`. Seções 17 e 19 do SDD.

Camada de núcleo (seção 6.2). `Settings` é a lista de variáveis da seção 17; o `.env.example`
repete a mesma lista, com o papel e o padrão de cada uma, e `tests/unit/test_layout.py`
confere que as duas listas são iguais. Quem usa: `app/core/container.py` (o `get_settings`,
lido uma vez por processo), `app/main.py`, os adaptadores, os scripts e o `alembic/env.py`,
que criam o próprio `Settings()`.

As proteções dos ambientes da Railway (`missing_safeguards`) ficam fora do `Settings` de
propósito: o `retention-job` lê a mesma configuração sem essas variáveis (seção 7.1).
"""

from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# O `.env` é procurado na pasta de onde o processo sobe, por isso os comandos rodam em
# `apps/api`. A conferência acontece uma vez, no import. Variável de ambiente vale mais que ele.
_ENV_FILE = ".env" if Path(".env").is_file() else None
# Os dois ambientes da Railway. Neles a API exige as proteções de `missing_safeguards`.
CLOUD_ENVIRONMENTS = frozenset({"development", "production"})


def rewrite_database_url(value: str) -> str:
    """Troca postgresql:// por postgresql+asyncpg://. Seção 17 do SDD.

    A Railway entrega a URL com `postgresql://`, sem driver no esquema, e o engine assíncrono
    da API precisa do asyncpg. Outro esquema, inclusive `postgresql+asyncpg://`, passa sem
    mudança, e a query string, como `sslmode`, fica como veio.
    """
    prefix = "postgresql://"
    if value.startswith(prefix):
        return "postgresql+asyncpg://" + value.removeprefix(prefix)
    return value


class Settings(BaseSettings):
    """Variáveis de ambiente da API, uma por campo. Seções 17 e 19 do SDD.

    O Pydantic Settings casa cada campo com a variável de mesmo nome, sem diferenciar
    maiúsculas (`app_env` lê `APP_ENV`), e converte o tipo: `LANGSMITH_TRACING=false` vira
    `False`. Um valor inválido levanta `ValidationError` ao criar o objeto. `extra="ignore"`
    deixa o `.env` ter outras chaves, como as do OpenTelemetry. O papel, o padrão e a
    obrigatoriedade de cada variável estão comentados no `.env.example`.
    """

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # `development` e `production` são os ambientes da Railway (`CLOUD_ENVIRONMENTS`).
    app_env: Literal["local", "test", "development", "production"] = "local"
    # Vazia, a API sobe e o `/health` responde; o `/ready` falha.
    database_url: str = ""
    gemini_api_key: str = ""
    chat_model: str = "gemini-2.5-flash"
    embedding_model: str = "gemini-embedding-2"
    # Precisa ser 768 na versão 1: a coluna é `vector(768)`, e o `/ready` confere (seção 8.3).
    embedding_dimensions: int = 768
    # O Strategy da seção 6.2: `app/adapters/chat_factory.py` e `embedding_factory.py` escolhem
    # o adaptador por este valor.
    app_ai_adapter: Literal["gemini", "fake", "demo"] = "gemini"
    web_origin: str = "http://localhost:5173"
    admin_email: str = ""
    admin_password: str = ""
    retrieval_min_similarity: float = 0.50
    # Zero desliga o teto. Só vale em `local` e `test` (seção 7.1).
    llm_daily_token_budget: int = 0
    metrics_token: str = ""
    rate_limit_hmac_key: str = ""
    pseudonym_key: str = ""
    edge_secret: str = ""
    privacy_contact_email: str = ""
    log_level: str = "INFO"
    # O atendimento humano da seção 29. Desligado por padrão; em production, só depois da
    # Etapa 17.8 (seção 29.14).
    handoff_enabled: bool = False
    # Os rastros só saem com `langsmith_tracing` verdadeiro e `langsmith_api_key` preenchida.
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
        """Reescreve o esquema antes da validação (`mode="before"`), com o valor ainda cru."""
        if isinstance(value, str):
            return rewrite_database_url(value)
        return value

    @model_validator(mode="after")
    def _demo_only_off_the_cloud(self) -> "Settings":
        """O modo `demo` responde por regras. Ele não pode chegar a um ambiente da Railway.

        Roda com todos os campos já lidos (`mode="after"`). O `ValueError` chega como
        `ValidationError`, então nem a API nem os scripts sobem com essa combinação (seção 17).
        """
        if self.app_ai_adapter == "demo" and self.app_env in CLOUD_ENVIRONMENTS:
            raise ValueError("APP_AI_ADAPTER=demo só vale com APP_ENV local ou test.")
        return self


class MissingSafeguards(RuntimeError):
    """A API não sobe na Railway sem o teto de tokens e as chaves de HMAC.

    Nem sem o segredo da borda. A mensagem cita todas as variáveis que faltam (seção 7.1), e
    `variables` guarda os nomes, na ordem de `missing_safeguards`, para os testes.
    """

    def __init__(self, app_env: str, variables: list[str]) -> None:
        super().__init__(
            f"APP_ENV={app_env} exige {', '.join(variables)}. "
            "LLM_DAILY_TOKEN_BUDGET precisa ser maior que zero, e as chaves não podem ficar "
            "vazias. Zero e vazio só valem com APP_ENV local ou test."
        )
        self.variables = tuple(variables)


def missing_safeguards(settings: Settings) -> list[str]:
    """Variáveis sem valor seguro para a API num ambiente da Railway. Seções 7.1, 10.3 e 10.4.

    O teto de tokens é a proteção de custo que os limites por IP não dão, e o segredo da borda
    impede que quem chama a Railway direto forje o IP desses limites. A regra vale para a API,
    não para todo `Settings`: o `retention-job` lê a mesma configuração sem essas variáveis.
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
    if not settings.edge_secret.strip():
        missing.append("EDGE_SECRET")
    return missing


def require_safeguards(settings: Settings) -> None:
    """Levanta `MissingSafeguards` quando falta alguma proteção. `create_app` chama na subida."""
    missing = missing_safeguards(settings)
    if missing:
        raise MissingSafeguards(settings.app_env, missing)


def edge_guard_secret(settings: Settings) -> str:
    """O segredo que a API exige em /v1. Seção 10.3 do SDD.

    Só vale em `development` e `production`: em `local` e `test`, o Vite faz o proxy sem o
    cabeçalho da Vercel. Nos ambientes da Railway, a API não sobe sem ele (`require_safeguards`).
    Fora deles devolve vazio, e o `ApiGuardMiddleware` deixa `/v1` aberto mesmo com
    `EDGE_SECRET` preenchido. O `strip` tira os espaços das pontas: o cabeçalho que chega é
    comparado com o valor sem eles.
    """
    if settings.app_env not in CLOUD_ENVIRONMENTS:
        return ""
    return settings.edge_secret.strip()
