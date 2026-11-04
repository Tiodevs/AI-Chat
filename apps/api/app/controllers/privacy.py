"""Canal do titular. Qualquer pessoa pode abrir um pedido. Seções 10.4, 11.5 e 12."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.adapters.password_hasher import get_password_hasher
from app.core.client_ip import client_ip
from app.core.config import Settings
from app.core.container import get_clock, get_settings
from app.domain.auth import SESSION_COOKIE_NAME
from app.domain.errors import Unauthenticated
from app.ports.clock import Clock
from app.schemas.errors import ErrorResponse
from app.schemas.privacy import PrivacyRequestCreate, PrivacyRequestResponse

router = APIRouter()

_ERRORS: dict[int | str, dict[str, Any]] = {
    403: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
}


@router.post(
    "/v1/privacy/requests",
    operation_id="createPrivacyRequest",
    status_code=201,
    responses=_ERRORS,
)
async def create_privacy_request(
    body: PrivacyRequestCreate,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> PrivacyRequestResponse:
    """Abre um pedido de titular com prazo de 15 dias. Limite de 5 por IP no dia."""
    from app.services.privacy import PrivacyRequestService

    record = await PrivacyRequestService(
        database_url=settings.database_url,
        clock=clock,
        hmac_key=settings.rate_limit_hmac_key,
    ).submit(
        contact_email=body.contact_email,
        request_type=body.request_type,
        description=body.description,
        client_ip=client_ip(
            request.headers.get("x-forwarded-for"),
            None if request.client is None else request.client.host,
        ),
        user_id=await _optional_user(request, settings, clock),
    )
    return PrivacyRequestResponse(
        id=record.id,
        request_type=record.request_type,
        status=record.status,
        received_at=record.received_at,
        due_at=record.due_at,
    )


async def _optional_user(request: Request, settings: Settings, clock: Clock) -> UUID | None:
    """Liga o pedido ao membro quando há sessão. Sem sessão, o pedido segue anônimo."""
    secret = request.cookies.get(SESSION_COOKIE_NAME)
    if not secret:
        return None
    from app.services.auth import AuthService

    try:
        profile = await AuthService(
            database_url=settings.database_url,
            clock=clock,
            hasher=get_password_hasher(),
            hmac_key=settings.rate_limit_hmac_key,
            app_env=settings.app_env,
        ).authenticate(secret)
    except Unauthenticated:
        return None
    return profile.id
