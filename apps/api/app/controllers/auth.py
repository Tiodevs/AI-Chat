"""Interpreta HTTP de autenticação e chama o serviço. Seções 10.3 e 12.

Camada de controle. Três rotas: `POST /v1/auth/login`, `POST /v1/auth/logout` e
`GET /v1/me`. Cada uma cria um `AuthService` com a configuração e o relógio do pedido, sem
passar pela raiz de composição, e o importa dentro da função, para o import da API não
carregar o SQLAlchemy. O cookie `atrium_session` é gravado e apagado por `app.core.cookies`.
A identidade vem só do cookie: o cabeçalho `Authorization` não identifica usuário (seção
10.3). As outras rotas de `/v1/me` ficam em `account.py`.

A docstring de cada rota é a `description` da operação no OpenAPI (seção 6.6); a explicação
a mais fica em comentários, para não mudar o contrato.
"""

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

# Status de erro documentados no OpenAPI, todos com o envelope `ErrorResponse`. A tabela só
# descreve o contrato; quem decide o status é `app.core.errors`.
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
    # O serviço conta o pedido nos baldes de login por e-mail e por IP (seção 10.4) e responde
    # o mesmo texto para e-mail inexistente e senha errada: 401 `unauthenticated`, ou 429
    # `rate_limited` acima do limite. No sucesso, abre uma sessão de 14 dias e devolve o
    # perfil de `GET /v1/me`. O argon2 roda no loop de eventos; a Etapa 13.1 o leva para uma
    # thread. O `response` injetado é onde o FastAPI junta o cookie antes de serializar o
    # perfil.
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
    # Responde 204. Sem cookie, ou com uma sessão já revogada, o serviço levanta
    # `Unauthenticated` (401), e o cookie fica no navegador. Só o `atrium_session` sai; a
    # Etapa 15.1 passa a apagar também o `atrium_guest`.
    from app.services.auth import AuthService

    await AuthService(
        database_url=settings.database_url,
        clock=clock,
        hasher=get_password_hasher(),
        hmac_key=settings.rate_limit_hmac_key,
        app_env=settings.app_env,
    ).logout(request.cookies.get(SESSION_COOKIE_NAME))
    # A rota devolve a própria `Response`, então o `Set-Cookie` que apaga o cookie vai nela.
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
    # `needs_legal_acceptance` é verdadeiro sem consentimento vigente de
    # `terms_and_privacy_notice` na versão atual (seção 12). Sem sessão válida, 401.
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
    """Converte o `Profile` do domínio no schema de resposta, que não tem `password_hash`."""
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
