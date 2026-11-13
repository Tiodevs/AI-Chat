"""Recebimento do webhook do WhatsApp: confere, grava e responde. Seções 30.2 e 30.4, ADR-017.

Camada de serviço. `controllers/whatsapp.py` chama `WhatsAppWebhookService` com o corpo cru
e o cabeçalho de assinatura. Nada de modelo, de rede nem de regra de negócio acontece aqui:
a rota só confere a assinatura, grava os eventos na caixa de entrada numa transação curta e
acorda o processador do próprio processo (NFR-21). O processador de outra réplica acha o
evento na próxima volta, em até 2 segundos.
"""

import json
from collections.abc import Callable
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import WHATSAPP_EVENTS, WHATSAPP_SIGNATURE_FAILURES
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.auth import bucket_key, fixed_window_start, retry_after_seconds
from app.domain.errors import Forbidden, RateLimited, ValidationFailed, WhatsAppBadSignature
from app.domain.whatsapp import (
    BAD_SIGNATURE_IP_LIMIT,
    BAD_SIGNATURE_IP_PURPOSE,
    BAD_SIGNATURE_WINDOW,
    MAX_WEBHOOK_BYTES,
    parse_webhook,
    verify_challenge,
    verify_signature,
)
from app.ports.clock import Clock
from app.prompts.whatsapp import BAD_SIGNATURE, BAD_VERIFY_TOKEN, TOO_LARGE, TOO_MANY
from app.repositories.rate_limits import RateLimitRepository
from app.repositories.whatsapp import WhatsAppRepository


class WhatsAppWebhookService:
    """Verificação e recebimento do webhook da Meta."""

    def __init__(
        self,
        *,
        database_url: str,
        clock: Clock,
        app_secret: str,
        verify_token: str,
        phone_number_id: str,
        hmac_key: str,
        wake: Callable[[], None] | None = None,
    ) -> None:
        self._database_url = database_url
        self._clock = clock
        self._app_secret = app_secret
        self._verify_token = verify_token
        self._phone_number_id = phone_number_id
        self._hmac_key = hmac_key
        self._wake = wake

    def verify(self, *, mode: str | None, token: str | None, challenge: str | None) -> str:
        """Devolve o desafio da Meta, ou 403 com outro token (seção 30.10)."""
        answer = verify_challenge(
            mode=mode, token=token, challenge=challenge, verify_token=self._verify_token
        )
        if answer is None:
            raise Forbidden(BAD_VERIFY_TOKEN)
        return answer

    async def receive(self, body: bytes, signature: str | None, client_ip: str) -> int:
        """Grava os eventos de um webhook assinado. Devolve quantos eram novos.

        1. Recusa corpo acima de 3 MB (422).
        2. Confere a assinatura sobre os bytes. Falha conta no balde por IP e responde 401,
           ou 429 acima de 30 por minuto, sem gravar nada.
        3. Lê o JSON e os eventos do número do Atrium. Um JSON que não se entende responde
           200 sem gravar, para a Meta não repetir para sempre.
        4. Grava os eventos novos numa transação, conta as métricas e acorda o processador.
        """
        # 1.
        if len(body) > MAX_WEBHOOK_BYTES:
            raise ValidationFailed(TOO_LARGE)
        # 2.
        if not verify_signature(body, signature, self._app_secret):
            WHATSAPP_SIGNATURE_FAILURES.inc()
            await self._count_bad_signature(client_ip)
            raise WhatsAppBadSignature(BAD_SIGNATURE)
        # 3.
        try:
            payload = json.loads(body)
        except ValueError:
            structlog.get_logger("atrium").warning("whatsapp.webhook_unreadable")
            return 0
        if not isinstance(payload, dict):
            return 0
        events = parse_webhook(payload, self._phone_number_id)
        if not events:
            return 0
        # 4.
        async with open_session(self._database_url) as session, UnitOfWork(session):
            inserted = await WhatsAppRepository(session).insert_events(events, self._clock.now())
        for event in events:
            WHATSAPP_EVENTS.labels(
                kind=event.kind.value,
                message_type="none" if event.message_type is None else event.message_type.value,
            ).inc()
        structlog.get_logger("atrium").info(
            "whatsapp.webhook_received", event_count=len(events), inserted=inserted
        )
        if inserted and self._wake is not None:
            self._wake()
        return inserted

    async def _count_bad_signature(self, client_ip: str) -> None:
        """Soma a falha no balde por IP. Acima do limite, levanta 429."""
        if not self._hmac_key or not self._database_url:
            return
        now = self._clock.now()
        window = fixed_window_start(now, BAD_SIGNATURE_WINDOW)
        async with open_session(self._database_url) as session, UnitOfWork(session):
            count = await _increment(session, client_ip, now, window, self._hmac_key)
        if count > BAD_SIGNATURE_IP_LIMIT:
            raise RateLimited(
                TOO_MANY,
                retry_after_seconds=retry_after_seconds(now, window, BAD_SIGNATURE_WINDOW),
            )


async def _increment(
    session: AsyncSession, client_ip: str, now: datetime, window: datetime, key: str
) -> int:
    """O contador do balde, com a chave HMAC do dia: o IP cru não é gravado."""
    return await RateLimitRepository(session).increment(
        bucket_key(
            purpose=BAD_SIGNATURE_IP_PURPOSE,
            subject=client_ip,
            day=now.astimezone(UTC).date(),
            key=key,
        ),
        window,
    )
