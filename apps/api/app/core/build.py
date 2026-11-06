"""Commit da imagem em execução. Seções 12 e 22.3 do SDD.

O `deploy.yml` grava o commit testado pela CI em `app/BUILD_SHA` antes do `railway up`. O
`/health` o devolve, e a fumaça espera a versão nova responder antes de testar, para nunca
aprovar a versão anterior que a Railway mantém no ar quando um deploy falha.

Sem o arquivo, vale `RAILWAY_GIT_COMMIT_SHA`, que a Railway preenche quando o serviço publica
a partir do repositório. Assim o `/health` mostra a versão no ar também nesse caminho, e um
rollback se confere com um pedido só (`docs/rollback.md`).
"""

import os
from functools import lru_cache
from pathlib import Path

_BUILD_FILE = Path(__file__).resolve().parents[1] / "BUILD_SHA"
_RAILWAY_COMMIT = "RAILWAY_GIT_COMMIT_SHA"
_MAX_CHARS = 64


def _valid(value: str) -> str | None:
    value = value.strip()
    if not value or len(value) > _MAX_CHARS or not value.isalnum():
        return None
    return value


@lru_cache(maxsize=1)
def build_sha() -> str | None:
    try:
        written = _valid(_BUILD_FILE.read_text(encoding="utf-8"))
    except OSError:
        written = None
    return written or _valid(os.environ.get(_RAILWAY_COMMIT, ""))
