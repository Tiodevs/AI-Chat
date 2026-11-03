"""Conta do membro: corrigir, exportar, consentimentos e excluir. Seções 11.5, 11.6 e 12."""

from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response

from app.adapters.password_hasher import get_password_hasher
from app.core.config import Settings
from app.core.container import get_clock, get_settings
from app.core.cookies import clear_session_cookie
from app.domain.auth import SESSION_COOKIE_NAME, session_cookie_is_secure
from app.domain.profile import Profile
from app.ports.clock import Clock
from app.prompts.account import EXPORT_FILENAME
from app.schemas.account import (
    ConsentChangeRequest,
    ConsentItemResponse,
    ConsentsResponse,
    ConsentStateResponse,
    ExportCitation,
    ExportConversation,
    ExportMessage,
    ExportProfile,
    ExportResponse,
    ProfilePatchRequest,
)
from app.schemas.auth import ProfileResponse
from app.schemas.errors import ErrorResponse

if TYPE_CHECKING:
    from app.services.account import AccountService, ConsentOverview, DataExport

router = APIRouter()

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


async def _profile(request: Request, settings: Settings, clock: Clock) -> Profile:
    from app.services.auth import AuthService

    return await AuthService(
        database_url=settings.database_url,
        clock=clock,
        hasher=get_password_hasher(),
        hmac_key=settings.rate_limit_hmac_key,
        app_env=settings.app_env,
    ).authenticate(request.cookies.get(SESSION_COOKIE_NAME))


def _service(settings: Settings, clock: Clock) -> "AccountService":
    from app.services.account import AccountService

    return AccountService(database_url=settings.database_url, clock=clock)


@router.patch("/v1/me", operation_id="updateMe", responses=_ERRORS)
async def update_me(
    body: ProfilePatchRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ProfileResponse:
    """Corrige o perfil. Só os campos enviados mudam, e `null` limpa um opcional."""
    profile = await _profile(request, settings, clock)
    updated = await _service(settings, clock).update_profile(
        profile.id, body.model_dump(exclude_unset=True)
    )
    return ProfileResponse(
        id=updated.id,
        email=updated.email,
        full_name=updated.full_name,
        phone=updated.phone,
        visitor_type=updated.visitor_type,
        visit_reason=updated.visit_reason,
        role=updated.role,
        needs_legal_acceptance=updated.needs_legal_acceptance,
    )


@router.get(
    "/v1/me/export",
    operation_id="exportMe",
    response_model=ExportResponse,
    responses=_ERRORS,
)
async def export_me(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> JSONResponse:
    """Exportação JSON do titular. Sem hashes, ids de rastro nem dados de outros titulares."""
    profile = await _profile(request, settings, clock)
    data = await _service(settings, clock).export(profile.id)
    return JSONResponse(
        content=_export_response(data).model_dump(mode="json"),
        headers={"Content-Disposition": f'attachment; filename="{EXPORT_FILENAME}"'},
    )


@router.get("/v1/me/consents", operation_id="getMyConsents", responses=_ERRORS)
async def get_consents(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ConsentsResponse:
    """Consentimentos vigentes e o histórico com as versões."""
    profile = await _profile(request, settings, clock)
    return _consents_response(await _service(settings, clock).consents(profile.id))


@router.put("/v1/me/consents/{purpose}", operation_id="setMyConsent", responses=_ERRORS)
async def set_consent(
    purpose: str,
    body: ConsentChangeRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ConsentsResponse:
    """Concede ou revoga. Revogar a personalização apaga o tipo de visitante e o motivo."""
    profile = await _profile(request, settings, clock)
    overview = await _service(settings, clock).set_consent(
        profile.id, purpose, granted=body.granted
    )
    return _consents_response(overview)


@router.delete(
    "/v1/me",
    operation_id="deleteMe",
    status_code=204,
    response_class=Response,
    responses=_ERRORS,
)
async def delete_me(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> Response:
    """Exclui a conta, as conversas e os consentimentos, e encerra a sessão."""
    profile = await _profile(request, settings, clock)
    await _service(settings, clock).delete_account(profile.id)
    response = Response(status_code=204)
    clear_session_cookie(response, secure=session_cookie_is_secure(settings.app_env))
    return response


def _consents_response(overview: "ConsentOverview") -> ConsentsResponse:
    return ConsentsResponse(
        current=[
            ConsentStateResponse(
                purpose=item.purpose,
                granted=item.granted,
                document_version=item.document_version,
                granted_at=item.granted_at,
            )
            for item in overview.current
        ],
        history=[
            ConsentItemResponse(
                purpose=item.purpose,
                document_version=item.document_version,
                granted_at=item.granted_at,
                revoked_at=item.revoked_at,
                source=item.source,
            )
            for item in overview.history
        ],
    )


def _export_response(data: "DataExport") -> ExportResponse:
    return ExportResponse(
        exported_at=data.exported_at,
        profile=ExportProfile(
            email=data.email,
            full_name=data.full_name,
            phone=data.phone,
            visitor_type=data.visitor_type,
            visit_reason=data.visit_reason,
            role=data.role,
            created_at=data.created_at,
        ),
        consents=[
            ConsentItemResponse(
                purpose=item.purpose,
                document_version=item.document_version,
                granted_at=item.granted_at,
                revoked_at=item.revoked_at,
                source=item.source,
            )
            for item in data.consents
        ],
        conversations=[
            ExportConversation(
                id=conversation.id,
                created_at=conversation.created_at,
                messages=[
                    ExportMessage(
                        role=message.role,
                        content=message.content,
                        citations=[
                            ExportCitation(
                                index=citation.index,
                                document_title=citation.document_title,
                                heading=citation.heading,
                            )
                            for citation in message.citations
                        ],
                        outcome=message.outcome,
                        feedback=message.feedback,
                        created_at=message.created_at,
                    )
                    for message in conversation.messages
                ],
            )
            for conversation in data.conversations
        ],
    )
