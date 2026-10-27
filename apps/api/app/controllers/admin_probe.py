"""Rota de admin usada só para provar a autorização até a Etapa 7."""

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
    from app.services.auth import AuthService

    await AuthService(
        database_url=settings.database_url,
        clock=clock,
        hasher=get_password_hasher(),
        hmac_key=settings.rate_limit_hmac_key,
        app_env=settings.app_env,
    ).require_admin(request.cookies.get(SESSION_COOKIE_NAME))
    return AdminProbeResponse(status="ok")
