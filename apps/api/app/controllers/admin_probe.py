"""Rota de admin usada só para provar a autorização até a Etapa 7.

Camada de controle. `GET /v1/admin/probe` responde `{"status": "ok"}` a um admin, 401 sem
sessão e 403 a um membro. Fica fora do OpenAPI (`include_in_schema=False`) e do contrato
público (seção 12). As rotas de admin da Etapa 7 já existem, e a Etapa 13.5 remove esta rota
e o teste dela. Repete o corpo de `admin_guard.require_admin` em vez de chamá-lo.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from app.adapters.password_hasher import get_password_hasher
from app.core.config import Settings
from app.core.container import get_clock, get_settings
from app.domain.auth import SESSION_COOKIE_NAME
from app.ports.clock import Clock
from app.schemas.auth import AdminProbeResponse
from app.schemas.errors import ErrorResponse

router = APIRouter()

# Status de erro para o OpenAPI. Como a rota fica fora do schema, a tabela não aparece nele.
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
}


@router.get(
    "/v1/admin/probe",
    operation_id="adminProbe",
    include_in_schema=False,
    responses=_ERRORS,
)
async def admin_probe(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> AdminProbeResponse:
    """Prova que o cookie é de um admin. Levanta `Unauthenticated` ou `Forbidden`."""
    from app.services.auth import AuthService

    await AuthService(
        database_url=settings.database_url,
        clock=clock,
        hasher=get_password_hasher(),
        hmac_key=settings.rate_limit_hmac_key,
        app_env=settings.app_env,
    ).require_admin(request.cookies.get(SESSION_COOKIE_NAME))
    return AdminProbeResponse(status="ok")
