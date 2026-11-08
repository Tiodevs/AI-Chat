from typing import Literal

import pytest

from app.core.config import (
    MissingSafeguards,
    Settings,
    missing_safeguards,
    require_safeguards,
    rewrite_database_url,
)
from app.core.container import get_settings
from app.main import create_app

AppEnv = Literal["local", "test", "development", "production"]


def test_rewrites_postgresql_scheme_to_asyncpg() -> None:
    original = "postgresql://user:secret@localhost:5432/atrium"
    assert rewrite_database_url(original) == (
        "postgresql+asyncpg://user:secret@localhost:5432/atrium"
    )


def test_settings_rewrite_database_url() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql://localhost:5432/atrium",
    )
    assert settings.database_url == "postgresql+asyncpg://localhost:5432/atrium"


def test_keeps_asyncpg_scheme() -> None:
    url = "postgresql+asyncpg://localhost:5432/atrium"
    assert rewrite_database_url(url) == url


def test_keeps_query_string() -> None:
    original = "postgresql://localhost:5432/atrium?sslmode=require"
    assert rewrite_database_url(original).endswith("?sslmode=require")


@pytest.mark.parametrize("app_env", ["development", "production"])
@pytest.mark.parametrize("budget", [0, -1])
def test_cloud_api_refuses_a_disabled_token_budget(app_env: AppEnv, budget: int) -> None:
    """Seção 7.1: zero desliga o teto, e o teto é o que segura o custo (seção 10.4)."""
    assert missing_safeguards(_settings(app_env, budget=budget)) == ["LLM_DAILY_TOKEN_BUDGET"]


@pytest.mark.parametrize("hmac_key", ["", "   "])
def test_cloud_api_refuses_an_empty_rate_limit_key(hmac_key: str) -> None:
    assert missing_safeguards(_settings(hmac_key=hmac_key)) == ["RATE_LIMIT_HMAC_KEY"]


@pytest.mark.parametrize("pseudonym_key", ["", "   "])
def test_cloud_api_refuses_an_empty_pseudonym_key(pseudonym_key: str) -> None:
    assert missing_safeguards(_settings(pseudonym_key=pseudonym_key)) == ["PSEUDONYM_KEY"]


@pytest.mark.parametrize("edge_secret", ["", "   "])
def test_cloud_api_refuses_an_empty_edge_secret(edge_secret: str) -> None:
    """Etapa 12.5b: sem o segredo da borda, quem chama a Railway direto forja o IP (seção 10.3)."""
    assert missing_safeguards(_settings(edge_secret=edge_secret)) == ["EDGE_SECRET"]


@pytest.mark.parametrize("app_env", ["local", "test"])
def test_local_and_test_accept_zero_budget_and_empty_keys(app_env: AppEnv) -> None:
    settings = _settings(app_env, budget=0, hmac_key="", pseudonym_key="", edge_secret="")
    assert missing_safeguards(settings) == []
    require_safeguards(settings)


@pytest.mark.parametrize("app_env", ["development", "production"])
def test_cloud_api_with_budget_and_keys_passes(app_env: AppEnv) -> None:
    settings = _settings(app_env)
    assert missing_safeguards(settings) == []
    require_safeguards(settings)


def test_the_error_names_every_missing_variable() -> None:
    with pytest.raises(MissingSafeguards) as raised:
        require_safeguards(_settings(budget=0, hmac_key="", pseudonym_key="", edge_secret=""))
    message = str(raised.value)
    assert raised.value.variables == (
        "LLM_DAILY_TOKEN_BUDGET",
        "RATE_LIMIT_HMAC_KEY",
        "PSEUDONYM_KEY",
        "EDGE_SECRET",
    )
    assert message.startswith("APP_ENV=production exige LLM_DAILY_TOKEN_BUDGET, ")
    assert "RATE_LIMIT_HMAC_KEY" in message
    assert "PSEUDONYM_KEY" in message


def test_api_does_not_start_in_production_with_the_budget_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CA-1 da Etapa 12.1: a API não sobe, e a mensagem diz qual variável falta."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("LLM_DAILY_TOKEN_BUDGET", "0")
    monkeypatch.setenv("RATE_LIMIT_HMAC_KEY", "hmac-key")
    monkeypatch.setenv("PSEUDONYM_KEY", "pseudonym-key")
    monkeypatch.setenv("EDGE_SECRET", "edge-secret")
    get_settings.cache_clear()
    with pytest.raises(MissingSafeguards, match="exige LLM_DAILY_TOKEN_BUDGET\\."):
        create_app()


def test_api_does_not_start_in_production_without_the_edge_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CA-1 da Etapa 12.5b: sem EDGE_SECRET, o deploy falha e a versão anterior fica no ar."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("LLM_DAILY_TOKEN_BUDGET", "1000")
    monkeypatch.setenv("RATE_LIMIT_HMAC_KEY", "hmac-key")
    monkeypatch.setenv("PSEUDONYM_KEY", "pseudonym-key")
    monkeypatch.setenv("EDGE_SECRET", "")
    get_settings.cache_clear()
    with pytest.raises(MissingSafeguards, match="exige EDGE_SECRET\\."):
        create_app()


def _settings(
    app_env: AppEnv = "production",
    *,
    budget: int = 2_000_000,
    hmac_key: str = "hmac-key",
    pseudonym_key: str = "pseudonym-key",
    edge_secret: str = "edge-secret",
) -> Settings:
    return Settings(
        _env_file=None,
        app_env=app_env,
        llm_daily_token_budget=budget,
        rate_limit_hmac_key=hmac_key,
        pseudonym_key=pseudonym_key,
        edge_secret=edge_secret,
    )
