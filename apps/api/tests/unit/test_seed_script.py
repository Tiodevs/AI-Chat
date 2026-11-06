"""Pré-deploy da Railway sem a chave do Gemini. Seção 22.1 do SDD, Etapa 10.1."""

import pytest

from app.prompts.corpus import MISSING_EMBEDDING_KEY, SEED_POSTPONED
from app.scripts import seed


@pytest.fixture(autouse=True)
def _gemini_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_AI_ADAPTER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("DATABASE_URL", "postgresql://atrium:atrium@127.0.0.1:5432/atrium")


def test_the_predeploy_mode_postpones_the_seed_and_succeeds(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Sem chave, o deploy segue. Embedar com o falso deixaria vetores que a semente não refaz."""
    seed.main(["--skip-without-key"])
    assert SEED_POSTPONED in capsys.readouterr().err


def test_without_the_flag_a_missing_key_still_fails(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        seed.main([])
    assert raised.value.code == 1
    assert MISSING_EMBEDDING_KEY in capsys.readouterr().err
