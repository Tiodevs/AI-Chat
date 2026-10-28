"""HTTP do cadastro. A senha não entra no log nem na transcrição. Seções 7.2 e 12."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from app.core.client_ip import client_ip
from app.core.container import get_registration_service
from app.core.context import current_request_id
from app.core.cookies import apply_session_cookie
from app.domain.questions import GUEST_COOKIE_NAME
from app.domain.registration import Acceptance
from app.schemas.auth import ProfileResponse
from app.schemas.errors import ErrorResponse
from app.schemas.registration import (
    AcceptanceRequest,
    FieldsPatchRequest,
    FormRequest,
    PasswordRequest,
    RegistrationFieldsResponse,
    RegistrationMessageRequest,
    RegistrationSessionResponse,
    ReviewRequest,
    TranscriptMessageResponse,
)

router = APIRouter()

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


@router.post(
    "/v1/registration/sessions",
    operation_id="startRegistration",
    status_code=201,
    responses=_ERRORS,
)
async def start_registration(
    service: Annotated[Any, Depends(get_registration_service)],
) -> RegistrationSessionResponse:
    """Começa um cadastro por chat e devolve a saudação."""
    return _session(await service.start())


@router.get(
    "/v1/registration/sessions/{session_id}",
    operation_id="getRegistration",
    responses=_ERRORS,
)
async def get_registration(
    session_id: UUID,
    service: Annotated[Any, Depends(get_registration_service)],
) -> RegistrationSessionResponse:
    """Status, campos entendidos, erros e o próximo passo."""
    return _session(await service.get(session_id))


@router.post(
    "/v1/registration/sessions/{session_id}/messages",
    operation_id="sendRegistrationMessage",
    responses=_ERRORS,
)
async def send_registration_message(
    session_id: UUID,
    body: RegistrationMessageRequest,
    request: Request,
    service: Annotated[Any, Depends(get_registration_service)],
) -> RegistrationSessionResponse:
    """Um turno do chat. A senha não passa por aqui."""
    view = await service.message(
        session_id,
        body.text,
        request_id=current_request_id(),
        client_ip=_ip(request),
    )
    return _session(view)


@router.patch(
    "/v1/registration/sessions/{session_id}/fields",
    operation_id="patchRegistrationFields",
    responses=_ERRORS,
)
async def patch_registration_fields(
    session_id: UUID,
    body: FieldsPatchRequest,
    service: Annotated[Any, Depends(get_registration_service)],
) -> RegistrationSessionResponse:
    """Edição direta no cartão de resumo, com as regras do formulário."""
    edits = {name: getattr(body, name) for name in body.model_fields_set}
    return _session(await service.patch_fields(session_id, edits))


@router.post(
    "/v1/registration/sessions/{session_id}/password",
    operation_id="setRegistrationPassword",
    responses=_ERRORS,
)
async def set_registration_password(
    session_id: UUID,
    body: PasswordRequest,
    request: Request,
    service: Annotated[Any, Depends(get_registration_service)],
) -> RegistrationSessionResponse:
    """Grava só o hash da senha e avança para a revisão."""
    view = await service.set_password(session_id, body.password, client_ip=_ip(request))
    return _session(view)


@router.post(
    "/v1/registration/sessions/{session_id}/review",
    operation_id="reviewRegistration",
    responses=_ERRORS,
)
async def review_registration(
    session_id: UUID,
    body: ReviewRequest,
    service: Annotated[Any, Depends(get_registration_service)],
) -> RegistrationSessionResponse:
    """Confirma o resumo ou volta para corrigir um campo."""
    return _session(await service.review(session_id, accept=body.accept))


@router.post(
    "/v1/registration/sessions/{session_id}/acceptance",
    operation_id="acceptRegistration",
    responses=_ERRORS,
)
async def accept_registration(
    session_id: UUID,
    body: AcceptanceRequest,
    request: Request,
    response: Response,
    service: Annotated[Any, Depends(get_registration_service)],
) -> ProfileResponse:
    """Registra os aceites, cria o membro e define o cookie."""
    result = await service.accept(
        session_id,
        _acceptance(body),
        user_agent=request.headers.get("user-agent", ""),
        guest_secret=request.cookies.get(GUEST_COOKIE_NAME),
    )
    return _profile(result, response)


@router.post(
    "/v1/registration/form",
    operation_id="submitRegistrationForm",
    responses=_ERRORS,
)
async def submit_registration_form(
    body: FormRequest,
    request: Request,
    response: Response,
    service: Annotated[Any, Depends(get_registration_service)],
) -> ProfileResponse:
    """Formulário completo. session_id é opcional. Usa a mesma conclusão do chat."""
    result = await service.submit_form(
        _form(body),
        user_agent=request.headers.get("user-agent", ""),
        guest_secret=request.cookies.get(GUEST_COOKIE_NAME),
        client_ip=_ip(request),
    )
    return _profile(result, response)


def _session(view: Any) -> RegistrationSessionResponse:
    return RegistrationSessionResponse(
        id=view.id,
        status=view.status,
        path=view.path,
        fields=RegistrationFieldsResponse(
            full_name=view.fields.full_name,
            email=view.fields.email,
            phone=view.fields.phone,
            visitor_type=view.fields.visitor_type,
            visit_reason=view.fields.visit_reason,
        ),
        field_errors=view.field_errors,
        next_step=view.next_step,
        prompt=view.prompt,
        messages=[
            TranscriptMessageResponse(role=item.role, text=item.text, created_at=item.created_at)
            for item in view.messages
        ],
        expires_at=view.expires_at,
    )


def _profile(result: Any, response: Response) -> ProfileResponse:
    apply_session_cookie(response, result.cookie)
    profile = result.profile
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


def _acceptance(body: AcceptanceRequest) -> Acceptance:
    return Acceptance(
        accept_terms=body.accept_terms,
        document_version=body.document_version,
        age_18_plus=body.age_18_plus,
        profile_personalization=body.profile_personalization,
        quality_improvement=body.quality_improvement,
    )


def _form(body: FormRequest) -> Any:
    from app.services.registration import FormInput

    return FormInput(
        session_id=body.session_id,
        full_name=body.full_name,
        email=body.email,
        phone=body.phone,
        visitor_type=body.visitor_type,
        visit_reason=body.visit_reason,
        password=body.password,
        accept_terms=body.accept_terms,
        document_version=body.document_version,
        age_18_plus=body.age_18_plus,
        profile_personalization=body.profile_personalization,
        quality_improvement=body.quality_improvement,
    )


def _ip(request: Request) -> str:
    return client_ip(
        request.headers.get("x-forwarded-for"),
        None if request.client is None else request.client.host,
    )
