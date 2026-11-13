"""Rotas do webhook do WhatsApp: verificação e recebimento. Seção 30.10 do SDD.

Camada de controle. As duas rotas só são montadas com `WHATSAPP_ENABLED` ligado (`main.py`).
Elas não leem cookie, não abrem sessão e passam pelo `ApiGuardMiddleware`: o segredo da borda
vale como em todo `/v1`, e a conferência de `Origin` fica de fora só neste caminho, porque a
Meta é autenticada pela assinatura do corpo (seção 30.4).

O `POST` lê o corpo cru, sem o FastAPI interpretar o JSON: a assinatura vale sobre os bytes
exatos que a Meta mandou. Depois de gravar, responde 200 com corpo vazio, inclusive para
tipos que o Atrium não trata, para a Meta não repetir (ADR-017).
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import PlainTextResponse

from app.core.client_ip import client_ip
from app.core.container import get_whatsapp_webhook_service
from app.domain.whatsapp import WEBHOOK_PATH
from app.schemas.errors import ErrorResponse

router = APIRouter()


@router.get(
    WEBHOOK_PATH,
    response_class=PlainTextResponse,
    responses={403: {"model": ErrorResponse}},
)
async def verify_webhook(
    service: Annotated[Any, Depends(get_whatsapp_webhook_service)],
    mode: Annotated[str | None, Query(alias="hub.mode")] = None,
    token: Annotated[str | None, Query(alias="hub.verify_token")] = None,
    challenge: Annotated[str | None, Query(alias="hub.challenge")] = None,
) -> PlainTextResponse:
    """A Meta confere o webhook: devolve o `hub.challenge` com o token certo, senão 403."""
    return PlainTextResponse(service.verify(mode=mode, token=token, challenge=challenge))


@router.post(
    WEBHOOK_PATH,
    status_code=200,
    response_class=Response,
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def receive_webhook(
    request: Request,
    service: Annotated[Any, Depends(get_whatsapp_webhook_service)],
) -> Response:
    """Confere a assinatura, grava os eventos e responde 200 sem corpo (NFR-21)."""
    body = await request.body()
    await service.receive(
        body,
        request.headers.get("x-hub-signature-256"),
        client_ip(
            request.headers.get("x-forwarded-for"),
            None if request.client is None else request.client.host,
        ),
    )
    return Response(status_code=200)
