"""HTTP do cadastro. A senha não entra no log nem na transcrição. Seções 7.2 e 12.

Camada de controle. As rotas recebem o `RegistrationService` de
`app.core.container.get_registration_service`. O id da sessão de cadastro no caminho é a
única credencial dela: as rotas não leem `atrium_session`, e quem tem o id continua o
cadastro. A senha só passa por `/password` e pelo formulário (FR-7). O aceite e o formulário
terminam na mesma conclusão do serviço e gravam o cookie `atrium_session` do membro novo.

Erros comuns a todas as rotas da sessão: 404 para um id que não existe e 422 para uma sessão
vencida ou abandonada, ou para um pedido fora do passo atual.

A docstring de cada rota é a `description` da operação no OpenAPI (seção 6.6); a explicação
a mais fica em comentários, para não mudar o contrato.
"""

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

# Status de erro documentados no OpenAPI, todos com o envelope `ErrorResponse`.
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
    # Responde 201. A saudação é cópia fixa de `app/prompts/registration.py`, sem chamar o
    # modelo (seção 12). Não conta no limite de taxa.
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
    # Conta no balde de 20 por hora por IP (429 acima). Com o orçamento estourado ou o
    # provedor fora, responde 503 (`degraded` ou `provider_unavailable`) sem gravar a mensagem
    # na transcrição, e a tela oferece o formulário (seção 7.2).
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
    # `model_fields_set` traz só os campos que vieram no corpo, mesmo os enviados como `null`,
    # e deixa de fora os ausentes. Não chama o modelo e não conta no limite de taxa.
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
    # Conta no balde de 20 por hora por IP. Uma senha fora de 12 a 72 caracteres volta em
    # `field_errors` com 200, sem avançar. O argon2 roda no loop de eventos; a Etapa 13.1 o
    # leva para uma thread.
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
    # Fora do passo de revisão, 422.
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
    # Sem os Termos na versão vigente ou sem a maioridade, 422 sem gravar usuário; e-mail já
    # usado, 409. As conversas da chave de convidado (`atrium_guest`) passam para o membro. A
    # chave de idempotência é o id da sessão: repetir o aceite de uma sessão concluída devolve
    # o mesmo membro com um cookie novo (seção 7.2).
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
    # Conta no balde de 20 por hora por IP. E-mail já usado responde 409 com
    # `field_errors.email`. Com o `session_id` de um cadastro já concluído, devolve o mesmo
    # membro com um cookie novo, como o aceite repetido.
    result = await service.submit_form(
        _form(body),
        user_agent=request.headers.get("user-agent", ""),
        guest_secret=request.cookies.get(GUEST_COOKIE_NAME),
        client_ip=_ip(request),
    )
    return _profile(result, response)


def _session(view: Any) -> RegistrationSessionResponse:
    """Converte a visão da sessão do serviço no schema da seção 12.

    Os itens da transcrição só têm papel, texto e data: não existe campo de senha (FR-7).
    """
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
    """Grava o cookie `atrium_session` da sessão nova e devolve o perfil de `GET /v1/me`."""
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
    """Converte o corpo do aceite no `Acceptance` do domínio, que confere os aceites."""
    return Acceptance(
        accept_terms=body.accept_terms,
        document_version=body.document_version,
        age_18_plus=body.age_18_plus,
        profile_personalization=body.profile_personalization,
        quality_improvement=body.quality_improvement,
    )


def _form(body: FormRequest) -> Any:
    """Converte o corpo do formulário no `FormInput` do serviço, importado só aqui."""
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
    """IP do cliente para os limites de taxa (`app.core.client_ip`)."""
    return client_ip(
        request.headers.get("x-forwarded-for"),
        None if request.client is None else request.client.host,
    )
