"""Commit da imagem em execução. Seções 12 e 22.3 do SDD.

O `deploy.yml` grava o commit testado pela CI em `app/BUILD_SHA` antes do `railway up`. O
`/health` o devolve, e a fumaça espera a versão nova responder antes de testar, para nunca
aprovar a versão anterior que a Railway mantém no ar quando um deploy falha.

Sem o arquivo, vale `RAILWAY_GIT_COMMIT_SHA`, que a Railway preenche quando o serviço publica
a partir do repositório. Assim o `/health` mostra a versão no ar também nesse caminho, e um
rollback se confere com um pedido só (`docs/rollback.md`).

Camada de núcleo. Quem usa: `app/controllers/health.py`.
"""

import os
from functools import lru_cache
from pathlib import Path

# `apps/api/app/BUILD_SHA`. O arquivo não está no repositório: só a imagem publicada o tem.
_BUILD_FILE = Path(__file__).resolve().parents[1] / "BUILD_SHA"
_RAILWAY_COMMIT = "RAILWAY_GIT_COMMIT_SHA"
# Seção 12: os dois valores só valem se forem alfanuméricos de até 64 caracteres.
_MAX_CHARS = 64


def _valid(value: str) -> str | None:
    """O commit sem espaços nas pontas, ou `None` se ele estiver vazio ou fora da regra."""
    value = value.strip()
    if not value or len(value) > _MAX_CHARS or not value.isalnum():
        return None
    return value


@lru_cache(maxsize=1)
def build_sha() -> str | None:
    """Commit da imagem em execução, ou `None` fora de um deploy.

    O arquivo `BUILD_SHA` vence o `RAILWAY_GIT_COMMIT_SHA`. Um arquivo ausente ou ilegível
    (`OSError`) cai na variável. O `lru_cache` lê uma vez por processo: a imagem não muda
    depois de subir.
    """
    try:
        written = _valid(_BUILD_FILE.read_text(encoding="utf-8"))
    except OSError:
        written = None
    return written or _valid(os.environ.get(_RAILWAY_COMMIT, ""))
