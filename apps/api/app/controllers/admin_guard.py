"""Exige a sessão de um admin nas rotas de /v1/admin. Seções 10.5 e 12 do SDD."""

from fastapi import Request

from app.adapters.password_hasher import get_password_hasher
from app.core.config import Settings
from app.domain.auth import SESSION_COOKIE_NAME
from app.domain.profile import Profile
from app.ports.clock import Clock


async def require_admin(request: Request, settings: Settings, clock: Clock) -> Profile:
    """Sem sessão, 401. Membro, 403."""
    from app.services.auth import AuthService

    return await AuthService(
        database_url=settings.database_url,
        clock=clock,
        hasher=get_password_hasher(),
        hmac_key=settings.rate_limit_hmac_key,
        app_env=settings.app_env,
    ).require_admin(request.cookies.get(SESSION_COOKIE_NAME))
