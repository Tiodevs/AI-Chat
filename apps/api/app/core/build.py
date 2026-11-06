"""Commit da imagem em execução. Seções 12 e 22.3 do SDD.

O `deploy.yml` grava o commit testado pela CI em `app/BUILD_SHA` antes do `railway up`. O
`/health` o devolve, e a fumaça espera a versão nova responder antes de testar, para nunca
aprovar a versão anterior que a Railway mantém no ar quando um deploy falha.
"""

from functools import lru_cache
from pathlib import Path

_BUILD_FILE = Path(__file__).resolve().parents[1] / "BUILD_SHA"
_MAX_CHARS = 64


@lru_cache(maxsize=1)
def build_sha() -> str | None:
    try:
        value = _BUILD_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not value or len(value) > _MAX_CHARS or not value.isalnum():
        return None
    return value
