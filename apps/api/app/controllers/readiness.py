"""GET /ready. Não usa o envelope de /v1: a sonda lê o status HTTP. Seção 12 do SDD.

Camada de controle. É o health check da Railway (seção 22.1): uma versão nova só entra no ar
quando esta rota responde 200, e até lá a anterior continua. Confere o que a NFR-9 pede: o
banco responde, a extensão `vector` existe e a coluna do embedding tem a dimensão da
configuração (seção 8.3). Fica fora de `/v1`, então o guarda da borda não a fecha. Cria o
`ReadinessService` aqui mesmo, sem passar pela raiz de composição.

A docstring da rota é a `description` da operação no OpenAPI (seção 6.6); a explicação a
mais fica em comentários.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.container import Container, get_container

router = APIRouter()


@router.get("/ready")
async def ready(container: Annotated[Container, Depends(get_container)]) -> JSONResponse:
    """Banco responde, a extensão vector está instalada e a dimensão confere."""
    # Devolve 200 `{"status": "ok"}` ou 503 `{"status": "unavailable"}`. O motivo da falha só
    # vai para o log `readiness.failed`. O serviço abre uma conexão própria, fora do pool,
    # para provar que o banco aceita conexão nova (seção 6.4).
    # Import tardio: carregar a aplicação para /health não puxa o driver do banco.
    from app.services.readiness import ReadinessService

    service = ReadinessService(
        container.settings.database_url,
        embedding_dimensions=container.settings.embedding_dimensions,
    )
    if await service.is_ready():
        return JSONResponse(status_code=200, content={"status": "ok"})
    return JSONResponse(status_code=503, content={"status": "unavailable"})
