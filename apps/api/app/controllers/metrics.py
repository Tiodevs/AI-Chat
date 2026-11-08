"""`GET /metrics`: texto Prometheus, protegido por token. Seção 18.3 do SDD.

Camada de controle. Fica fora de `/v1` e do OpenAPI (`include_in_schema=False`). O Prometheus
da Railway chama a rota pela rede privada, sem o segredo da borda. É a única rota que lê o
cabeçalho `Authorization` (seção 10.3). Responde 404 e 401 com `HTTPException`, no formato
padrão do FastAPI, fora do envelope da seção 12.
"""

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST

from app.core.container import Container, get_clock, get_container
from app.core.metrics import render_metrics
from app.ports.clock import Clock

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
async def metrics(
    container: Annotated[Container, Depends(get_container)],
    clock: Annotated[Clock, Depends(get_clock)],
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    """Métricas do Prometheus. Desligada sem METRICS_TOKEN. Seção 18.3.

    1. Sem `METRICS_TOKEN`, responde 404, como se a rota não existisse.
    2. Compara o token de `Authorization: Bearer` em tempo constante; errado ou ausente, 401.
    3. Relê do banco as séries de titular e de retenção. Uma falha do banco mantém o último
       valor e não derruba a rota.
    4. Devolve o registro da API no formato de texto do Prometheus.

    `Header()` liga o parâmetro `authorization` ao cabeçalho `Authorization`.
    """
    # 1.
    expected = container.settings.metrics_token
    if not expected:
        raise HTTPException(status_code=404)
    # 2. `compare_digest` leva o mesmo tempo com qualquer token errado: a demora da resposta
    # não revela quantos caracteres acertaram.
    supplied = (authorization or "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Bearer"})
    # 3. Import tardio: subir a API para /health não carrega o SQLAlchemy.
    from app.services.ops_metrics import refresh_database_metrics

    await refresh_database_metrics(container.settings.database_url, clock)
    # 4.
    return Response(render_metrics(), media_type=CONTENT_TYPE_LATEST)
