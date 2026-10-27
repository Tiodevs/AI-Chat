"""Interpreta HTTP de autenticação e chama o serviço. Seções 10.3 e 12."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from app.adapters.password_hasher import get_password_hasher
from app.core.client_ip import client_ip
from app.core.config import Settings
from app.core.container import get_clock, get_settings
from app.core.cookies import apply_session_cookie, clear_session_cookie
from app.domain.auth import SESSION_COOKIE_NAME, session_cookie_is_secure
from app.domain.profile import Profile
from app.ports.clock import Clock
from app.schemas.auth import LoginRequest, ProfileResponse
from app.schemas.errors import ErrorResponse

router = APIRouter()

_AUTH_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
}


@router.post(
    "/v1/auth/login",
    operation_id="login",
    responses=_AUTH_ERRORS,
)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ProfileResponse:
    """E-mail e senha. Define o cookie atrium_session."""
    from app.services.auth import AuthService

    result = await AuthService(
        database_url=settings.database_url,
        clock=clock,
        hasher=get_password_hasher(),
        hmac_key=settings.rate_limit_hmac_key,
        app_env=settings.app_env,
    ).login(
        email=body.email,
        password=body.password,
        user_agent=request.headers.get("user-agent", ""),
        client_ip=client_ip(
            request.headers.get("x-forwarded-for"),
            None if request.client is None else request.client.host,
        ),
    )
    apply_session_cookie(response, result.cookie)
    return _profile_response(result.profile)


@router.post(
    "/v1/auth/logout",
    operation_id="logout",
    status_code=204,
    response_class=Response,
    responses=_AUTH_ERRORS,
)
async def logout(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> Response:
    """Revoga a sessão e apaga o cookie."""
    from app.services.auth import AuthService

    await AuthService(
        database_url=settings.database_url,
        clock=clock,
        hasher=get_password_hasher(),
        hmac_key=settings.rate_limit_hmac_key,
        app_env=settings.app_env,
    ).logout(request.cookies.get(SESSION_COOKIE_NAME))
    body = Response(status_code=204)
    clear_session_cookie(body, secure=session_cookie_is_secure(settings.app_env))
    return body


@router.get(
    "/v1/me",
    operation_id="getMe",
    responses=_AUTH_ERRORS,
)
async def me(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ProfileResponse:
    """Perfil de quem está na sessão e se há documento legal novo."""
    from app.services.auth import AuthService

    profile = await AuthService(
        database_url=settings.database_url,
        clock=clock,
        hasher=get_password_hasher(),
        hmac_key=settings.rate_limit_hmac_key,
        app_env=settings.app_env,
    ).authenticate(request.cookies.get(SESSION_COOKIE_NAME))
    return _profile_response(profile)


def _profile_response(profile: Profile) -> ProfileResponse:
    return ProfileResponse(
        id=profile.id,
        email=profile.email,
        full_name=profile.full_name,
        phone=profile.phone,
        visitor_type=profile.visitor_type,
        visit_reason=profile.visit_reason,
        role=profile.role,
        needs_legal_acceptance=profile.needs_legal_acceptance,
    )
