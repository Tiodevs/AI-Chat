"""`GET /health`: o processo está no ar e qual commit roda. Seções 12 e 22.3 do SDD.

Camada de controle, sem serviço. A rota não toca no banco e não importa nada que o carregue:
responde com o banco fora, e o deploy espera aqui o commit novo antes da fumaça
(`app/core/build.py`). Fica fora de `/v1`, então o `ApiGuardMiddleware` não pede o segredo
da borda, e a Railway e a fumaça chamam a rota direto.

A docstring da rota é a `description` da operação no OpenAPI (seção 6.6): mudar o texto
muda o contrato que o job `contract` confere. A explicação a mais fica em comentários.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.build import build_sha
from app.core.container import Container, get_container

router = APIRouter()


@router.get("/health")
async def health(_: Annotated[Container, Depends(get_container)]) -> dict[str, str | None]:
    """O processo está no ar, com o commit da imagem. Esta rota não abre conexão com o banco."""
    # Devolve `{"status": "ok", "build": <commit ou null>}`. O `Container` pedido em `_` não é
    # lido.
    return {"status": "ok", "build": build_sha()}
