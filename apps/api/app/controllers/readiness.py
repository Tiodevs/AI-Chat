"""GET /ready. Não usa o envelope de /v1: a sonda lê o status HTTP. Seção 12 do SDD."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.container import Container, get_container

router = APIRouter()


@router.get("/ready")
async def ready(container: Annotated[Container, Depends(get_container)]) -> JSONResponse:
    """Banco responde e a extensão vector está instalada."""
    # Import tardio: carregar a aplicação para /health não puxa o driver do banco.
    from app.services.readiness import ReadinessService

    service = ReadinessService(container.settings.database_url)
    if await service.is_ready():
        return JSONResponse(status_code=200, content={"status": "ok"})
    return JSONResponse(status_code=503, content={"status": "unavailable"})
