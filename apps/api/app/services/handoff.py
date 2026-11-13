"""Atendimento humano pelo lado do visitante: pedir, escrever, encerrar e acompanhar.

Camada de serviço. Seções 29.4, 29.5, 29.6, 29.8 e 29.9.7 do SDD. `controllers/handoff.py`
monta o `HandoffService` por pedido (`core/container.py:get_handoff_service`). Usa
`HandoffRepository`, `ConversationRepository` e `RateLimitRepository`, as regras de
`domain/handoff.py` e `domain/redaction.py`, e a porta `RealtimeBroker`.

Nenhuma rota daqui recebe o provedor de chat, o de embedding ou o `FeedbackSink`: o texto do
atendimento não vai ao Gemini nem ao LangSmith (FR-21, NFR-17). Cada gravação faz o `NOTIFY`
na mesma transação, e o serviço chama `broker.committed` depois do commit.

O fluxo `GET /v1/conversations/{id}/handoff/events` é um `VisitorStream`: manda `ready`, as
mensagens com `seq` maior que o do `Last-Event-ID`, e depois acorda a cada aviso e a cada
tique de 15 segundos. O tique confere de novo a sessão e o dono, grava `visitor_seen_at` e
lê o que um aviso perdido não trouxe. Aos 10 minutos, o fluxo manda `reconnect` e fecha.
"""

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import HANDOFF_CLOSED, HANDOFF_MESSAGES, HANDOFF_REDACTIONS, HANDOFF_REQUESTS
from app.core.sse import (
    DISCONNECTED,
    KEEPALIVE,
    KEEPALIVE_COMMENT,
    format_comment,
    format_event,
    message_event_id,
    next_stream_item,
    parse_last_event_id,
)
from app.core.telemetry import traced_span
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.auth import RateDecision, bucket_key, fixed_window_start, retry_after_seconds
from app.domain.errors import (
    DomainError,
    DuplicateMessage,
    HandoffActive,
    HandoffBlocked,
    HandoffClosed,
    HandoffNotOffered,
    HandoffUnavailable,
    NotFound,
    RateLimited,
    ValidationFailed,
)
from app.domain.handoff import (
    HANDOFF_WINDOW,
    MAX_VISITOR_CHARS,
    REQUEST_IP_LIMIT,
    REQUEST_IP_PURPOSE,
    REQUEST_SUBJECT_LIMIT,
    REQUEST_SUBJECT_PURPOSE,
    STREAM_MAX_SECONDS,
    STREAM_TICK_SECONDS,
    VISITOR_MESSAGE_LIMIT,
    VISITOR_MESSAGE_PURPOSE,
    Availability,
    HandoffNotice,
    HandoffStatus,
    availability,
    clean_message,
    close_reason_for_visitor,
    handoff_offer,
    is_blocked,
    queue_position,
)
from app.domain.redaction import redact_identifiers
from app.ports.clock import Clock
from app.ports.realtime import RealtimeBroker
from app.prompts.conversations import CONVERSATION_NOT_FOUND
from app.prompts.handoff import (
    ACTIVE_ELSEWHERE,
    BLOCKED,
    CLOSED,
    DUPLICATE,
    HANDOFF_NOT_FOUND,
    INVALID_TEXT,
    NOT_OFFERED,
    RATE_LIMITED,
    REQUEST_RATE_LIMITED,
    STREAM_REVOKED,
    UNAVAILABLE,
)
from app.repositories.conversations import ConversationRepository
from app.repositories.handoffs import (
    HandoffMessageConflict,
    HandoffMessageRecord,
    HandoffRecord,
    HandoffRepository,
)
from app.repositories.rate_limits import RateLimitRepository
from app.services.stream_limits import LIMITER, StreamLease
from app.services.visitor import Visitor, resolve_visitor


@dataclass(frozen=True, slots=True)
class HandoffView:
    """O atendimento como o visitante o vê (seção 29.10). Sem quem atende (D-9)."""

    id: UUID
    status: str
    queue_position: int | None
    close_reason: str | None
    requested_at: datetime
    assigned_at: datetime | None
    closed_at: datetime | None
    seq: int


class HandoffService:
    """Casos de uso do visitante no atendimento humano.

    `enabled` é o `HANDOFF_ENABLED` da seção 29.14. `hmac_key` é a `RATE_LIMIT_HMAC_KEY` dos
    baldes da seção 29.8. `broker` entrega os avisos aos fluxos deste processo.
    """

    def __init__(
        self,
        *,
        database_url: str,
        clock: Clock,
        hmac_key: str,
        enabled: bool,
        broker: RealtimeBroker,
    ) -> None:
        self._database_url = database_url
        self._clock = clock
        self._hmac_key = hmac_key
        self._enabled = enabled
        self._broker = broker

    async def availability(self) -> Availability:
        """O status único de `GET /v1/handoff/availability`, sem contar pessoas (29.4)."""
        if not self._enabled:
            return Availability.DISABLED
        async with open_session(self._database_url) as session, UnitOfWork(session):
            return await self._availability(HandoffRepository(session))

    async def request(
        self,
        conversation_id: UUID,
        *,
        trigger_message_id: UUID,
        session_secret: str | None,
        guest_secret: str | None,
        client_ip: str,
        visitor: Visitor | None = None,
    ) -> tuple[HandoffView, bool]:
        """Pede o atendimento. Devolve o atendimento e se ele foi criado agora (201 ou 200).

        As conferências seguem a ordem da seção 29.5, passo 1:

        1. Visitante (401) e, numa transação própria, a tentativa contada nos baldes de 3 por
           hora por visitante e 10 por hora por IP, confirmada mesmo quando o pedido falha.
        2. Numa transação: dono da conversa (404), atendimento ativo nesta conversa (devolve o
           mesmo), `HANDOFF_ENABLED` (503), atendimento ativo do visitante em outra conversa
           (409 `handoff_active`), bloqueio por abuso (403), limite (429), a regra da oferta
           (409 `handoff_not_offered`) e a disponibilidade (503).
        3. Grava o atendimento `queued` com o `trigger` e o `NOTIFY`, na mesma transação.
        4. Depois do commit, entrega o aviso aos fluxos do processo e conta a métrica.
        """
        # 1. O canal WhatsApp passa o visitante já resolvido: o contato não tem cookie.
        self._require_hmac()
        visitor = visitor or await self._visitor(session_secret, guest_secret)
        now = self._clock.now()
        rate = await self._count_request(visitor, client_ip, now)
        created = False
        trigger = ""
        notices: list[HandoffNotice] = []
        error: DomainError | None = None
        view: HandoffView | None = None
        # 2.
        with traced_span("handoff.request") as span:
            async with open_session(self._database_url) as session, UnitOfWork(session):
                handoffs = HandoffRepository(session)
                await self._owned_conversation(session, visitor, conversation_id)
                current = await handoffs.active_for_conversation(conversation_id)
                if current is not None:
                    view = await self._view(handoffs, current)
                else:
                    await handoffs.lock_key(visitor.subject_id)
                    record, error = await self._checked_request(
                        handoffs,
                        visitor=visitor,
                        conversation_id=conversation_id,
                        trigger_message_id=trigger_message_id,
                        rate=rate,
                        now=now,
                    )
                    if record is not None:
                        # 3.
                        created = True
                        trigger = record.trigger
                        span.set(trigger=trigger)
                        view = await self._view(handoffs, record)
                        notices = list(handoffs.notices)
        if error is not None:
            raise error
        if view is None:
            raise NotFound(HANDOFF_NOT_FOUND)
        # 4.
        if created:
            await self._broker.committed(notices)
            HANDOFF_REQUESTS.labels(trigger=trigger).inc()
            structlog.get_logger("atrium").info(
                "handoff.requested",
                handoff_id=str(view.id),
                conversation_id=str(conversation_id),
            )
        return view, created

    async def current(
        self,
        conversation_id: UUID,
        *,
        session_secret: str | None,
        guest_secret: str | None,
    ) -> HandoffView:
        """O atendimento ativo ou o último da conversa. Sem nenhum, 404 (seção 29.10)."""
        visitor = await self._visitor(session_secret, guest_secret)
        async with open_session(self._database_url) as session, UnitOfWork(session):
            await self._owned_conversation(session, visitor, conversation_id)
            handoffs = HandoffRepository(session)
            record = await handoffs.latest_for_conversation(conversation_id)
            if record is None:
                raise NotFound(HANDOFF_NOT_FOUND)
            return await self._view(handoffs, record)

    async def send(
        self,
        conversation_id: UUID,
        *,
        text: str,
        client_message_id: UUID,
        session_secret: str | None,
        guest_secret: str | None,
        visitor: Visitor | None = None,
    ) -> HandoffMessageRecord:
        """Grava a mensagem do visitante, já sem identificadores (seções 29.5 e 29.9.7).

        1. Confere o texto: de 1 a 1.000 caracteres, sem caractere de controle (422).
        2. Numa transação: dono (404), o atendimento (404 sem nenhum, 409 encerrado), o
           reenvio do mesmo `client_message_id` (409 com `message_id`) e o balde de 120 por
           hora por atendimento.
        3. Remove os identificadores e grava com o próximo `seq` e o `NOTIFY`.
        4. Depois do commit, entrega o aviso e conta as métricas, sem o texto.
        """
        # 1.
        cleaned = clean_message(text, MAX_VISITOR_CHARS)
        if cleaned is None:
            raise ValidationFailed(INVALID_TEXT.format(max_chars=MAX_VISITOR_CHARS))
        self._require_hmac()
        visitor = visitor or await self._visitor(session_secret, guest_secret)
        now = self._clock.now()
        redacted = redact_identifiers(cleaned)
        limited: RateDecision | None = None
        stored: HandoffMessageRecord | None = None
        notices: list[HandoffNotice] = []
        # 2.
        with traced_span("handoff.message", role="user") as span:
            try:
                async with open_session(self._database_url) as session, UnitOfWork(session):
                    await self._owned_conversation(session, visitor, conversation_id)
                    handoffs = HandoffRepository(session)
                    record = await handoffs.latest_for_conversation(conversation_id)
                    if record is None:
                        raise NotFound(HANDOFF_NOT_FOUND)
                    if record.status == HandoffStatus.CLOSED:
                        raise HandoffClosed(CLOSED)
                    decision = await self._consume(
                        session, VISITOR_MESSAGE_PURPOSE, str(record.id), VISITOR_MESSAGE_LIMIT, now
                    )
                    if decision.limited:
                        limited = decision
                    else:
                        # 3.
                        stored = await handoffs.append_message(
                            handoff_id=record.id,
                            conversation_id=conversation_id,
                            role="user",
                            content=redacted.text,
                            client_message_id=client_message_id,
                            author_user_id=None,
                            now=now,
                        )
                        notices = list(handoffs.notices)
            except HandoffMessageConflict as exc:
                raise DuplicateMessage(DUPLICATE, message_id=exc.message_id) from None
            span.set(redaction_count=redacted.total)
        if limited is not None:
            raise RateLimited(RATE_LIMITED, retry_after_seconds=limited.retry_after_seconds)
        if stored is None:
            raise HandoffClosed(CLOSED)
        # 4.
        await self._broker.committed(notices)
        HANDOFF_MESSAGES.labels(role="user").inc()
        for kind, count in redacted.counts.items():
            HANDOFF_REDACTIONS.labels(kind=kind.value).inc(count)
        return stored

    async def end(
        self,
        conversation_id: UUID,
        *,
        session_secret: str | None,
        guest_secret: str | None,
        visitor: Visitor | None = None,
    ) -> HandoffView:
        """O visitante sai da fila ou encerra o atendimento (FR-24). Repetir devolve o mesmo.

        Na fila, o motivo é `visitor_cancelled`; em atendimento, `visitor_ended`. Sem nenhum
        atendimento, 404. O canal WhatsApp passa o `visitor` do contato.
        """
        visitor = visitor or await self._visitor(session_secret, guest_secret)
        now = self._clock.now()
        notices: list[HandoffNotice] = []
        closed: HandoffRecord | None = None
        async with open_session(self._database_url) as session, UnitOfWork(session):
            await self._owned_conversation(session, visitor, conversation_id)
            handoffs = HandoffRepository(session)
            record = await handoffs.latest_for_conversation(conversation_id)
            if record is None:
                raise NotFound(HANDOFF_NOT_FOUND)
            if record.status != HandoffStatus.CLOSED:
                closed = await handoffs.close(
                    record.id, reason=close_reason_for_visitor(record.status), now=now
                )
                notices = list(handoffs.notices)
            final = closed or await handoffs.get(record.id) or record
            view = await self._view(handoffs, final)
        if closed is not None:
            await self._broker.committed(notices)
            count_close(closed)
        return view

    async def open_stream(
        self,
        conversation_id: UUID,
        *,
        session_secret: str | None,
        guest_secret: str | None,
        last_event_id: str | None,
    ) -> "VisitorStream":
        """Confere tudo antes do primeiro byte do fluxo, para os erros saírem como JSON.

        Visitante (401), dono (404), algum atendimento na conversa (404) e a vaga do fluxo,
        3 por conversa e 300 no processo (429). Um `Last-Event-ID` de outro atendimento é
        ignorado (seção 29.6).
        """
        visitor = await self._visitor(session_secret, guest_secret)
        async with open_session(self._database_url) as session, UnitOfWork(session):
            await self._owned_conversation(session, visitor, conversation_id)
            record = await HandoffRepository(session).latest_for_conversation(conversation_id)
        if record is None:
            raise NotFound(HANDOFF_NOT_FOUND)
        resume = parse_last_event_id(last_event_id)
        after_seq = resume[1] if resume is not None and resume[0] == record.id else 0
        lease = LIMITER.acquire("handoff", str(conversation_id))
        return VisitorStream(
            service=self,
            conversation_id=conversation_id,
            handoff_id=record.id,
            session_secret=session_secret,
            guest_secret=guest_secret,
            after_seq=after_seq,
            lease=lease,
        )

    async def _checked_request(
        self,
        handoffs: HandoffRepository,
        *,
        visitor: Visitor,
        conversation_id: UUID,
        trigger_message_id: UUID,
        rate: RateDecision,
        now: datetime,
    ) -> tuple[HandoffRecord | None, DomainError | None]:
        """As conferências do passo 2 a partir do serviço ligado, e a gravação do passo 3.

        Devolve o atendimento criado ou o erro, que o chamador levanta depois de a transação
        fechar. Nenhuma gravação acontece quando há erro.
        """
        if not self._enabled:
            return None, HandoffUnavailable(UNAVAILABLE, availability=Availability.DISABLED)
        other = await handoffs.active_for_subject(
            user_id=visitor.user_id, guest_key_id=visitor.guest_key_id
        )
        if other is not None:
            return None, HandoffActive(
                ACTIVE_ELSEWHERE, handoff_id=other.id, conversation_id=other.conversation_id
            )
        abusive_at = await handoffs.last_abusive_close(
            user_id=visitor.user_id, guest_key_id=visitor.guest_key_id
        )
        if is_blocked(abusive_at, now):
            return None, HandoffBlocked(BLOCKED)
        if rate.limited:
            return None, RateLimited(
                REQUEST_RATE_LIMITED, retry_after_seconds=rate.retry_after_seconds
            )
        last = await handoffs.last_answer(conversation_id)
        trigger = None
        if last is not None and last.message_id == trigger_message_id:
            trigger = handoff_offer(
                last.outcome, rated_not_helpful=last.rated_not_helpful, handoff_active=False
            )
        if trigger is None:
            return None, HandoffNotOffered(NOT_OFFERED)
        status = await self._availability(handoffs)
        if status is not Availability.OPEN:
            return None, HandoffUnavailable(UNAVAILABLE, availability=status.value)
        record = await handoffs.insert(
            conversation_id=conversation_id,
            trigger=trigger.value,
            trigger_message_id=trigger_message_id,
            now=now,
        )
        return record, None

    async def _availability(self, handoffs: HandoffRepository) -> Availability:
        """O status da seção 29.4, lido na transação de quem chama."""
        now = self._clock.now()
        return availability(
            enabled=self._enabled,
            attendants_present=await handoffs.count_present_staff(now),
            queued=await handoffs.count_queued(),
        )

    async def _count_request(self, visitor: Visitor, client_ip: str, now: datetime) -> RateDecision:
        """Conta a tentativa nos dois baldes do pedido, numa transação que sempre confirma."""
        async with open_session(self._database_url) as session, UnitOfWork(session):
            by_subject = await self._consume(
                session,
                REQUEST_SUBJECT_PURPOSE,
                str(visitor.subject_id),
                REQUEST_SUBJECT_LIMIT,
                now,
            )
            by_ip = await self._consume(
                session, REQUEST_IP_PURPOSE, client_ip, REQUEST_IP_LIMIT, now
            )
        if by_subject.limited or by_ip.limited:
            return RateDecision(
                limited=True,
                retry_after_seconds=max(by_subject.retry_after_seconds, by_ip.retry_after_seconds),
            )
        return RateDecision(limited=False, retry_after_seconds=0)

    async def _consume(
        self,
        session: AsyncSession,
        purpose: str,
        subject: str,
        limit: int,
        now: datetime,
    ) -> RateDecision:
        """Soma 1 no balde por hora e decide o 429. A chave é HMAC com o sal do dia."""
        window = fixed_window_start(now, HANDOFF_WINDOW)
        count = await RateLimitRepository(session).increment(
            bucket_key(
                purpose=purpose,
                subject=subject,
                day=now.astimezone(UTC).date(),
                key=self._hmac_key,
            ),
            window,
        )
        if count <= limit:
            return RateDecision(limited=False, retry_after_seconds=0)
        return RateDecision(
            limited=True,
            retry_after_seconds=retry_after_seconds(now, window, HANDOFF_WINDOW),
        )

    async def _owned_conversation(
        self, session: AsyncSession, visitor: Visitor, conversation_id: UUID
    ) -> None:
        """A conversa existe e é do visitante. Senão, o mesmo 404 (seção 29.8)."""
        conversation = await ConversationRepository(session).get_conversation(conversation_id)
        if conversation is None or not visitor.owns(conversation):
            raise NotFound(CONVERSATION_NOT_FOUND)

    async def _view(self, handoffs: HandoffRepository, record: HandoffRecord) -> HandoffView:
        """O atendimento com a posição na fila, só quando está na fila."""
        position = None
        if record.status == HandoffStatus.QUEUED:
            position = queue_position(await handoffs.queue_ahead(record))
        return HandoffView(
            id=record.id,
            status=record.status,
            queue_position=position,
            close_reason=record.close_reason,
            requested_at=record.requested_at,
            assigned_at=record.assigned_at,
            closed_at=record.closed_at,
            seq=record.last_seq,
        )

    async def _visitor(self, session_secret: str | None, guest_secret: str | None) -> Visitor:
        """Resolve o visitante pelos dois cookies (401 sem nenhum válido)."""
        return await resolve_visitor(
            self._database_url,
            self._clock,
            session_secret=session_secret,
            guest_secret=guest_secret,
        )

    def _require_hmac(self) -> None:
        """Sem `RATE_LIMIT_HMAC_KEY` não há balde: falha como erro de servidor."""
        if not self._hmac_key:
            raise RuntimeError("RATE_LIMIT_HMAC_KEY vazio.")


class VisitorStream:
    """O fluxo SSE do visitante, de `ready` a `reconnect` (seção 29.6).

    Guarda os cookies do pedido para conferir a sessão e o dono a cada tique. Não segura
    conexão do pool entre um tique e outro: cada leitura abre e fecha uma transação curta.
    """

    def __init__(
        self,
        *,
        service: HandoffService,
        conversation_id: UUID,
        handoff_id: UUID,
        session_secret: str | None,
        guest_secret: str | None,
        after_seq: int,
        lease: StreamLease,
    ) -> None:
        self._service = service
        self._conversation_id = conversation_id
        self._handoff_id = handoff_id
        self._session_secret = session_secret
        self._guest_secret = guest_secret
        self._sent_seq = after_seq
        self._lease = lease
        self._last_status: tuple[str, int | None, str | None] | None = None

    async def events(self, disconnected: asyncio.Event) -> AsyncIterator[str]:
        """Os eventos do fluxo, já em texto SSE.

        1. `ready` com o estado atual e o último `seq`, e as mensagens com `seq` maior que o
           do `Last-Event-ID`, em ordem.
        2. Espera o próximo aviso, o tique ou a desconexão. Um aviso deste atendimento, ou da
           fila, faz ler de novo; o tique também confere a sessão e o dono, grava o sinal e
           manda `: keepalive`.
        3. Uma mudança de status ou de posição vira `status`. Encerrado, o fluxo fecha.
        4. Aos 10 minutos, `reconnect`, e o fluxo fecha. Uma sessão que deixou de valer manda
           `error` e fecha.
        """
        queue = self._service._broker.subscribe()
        started = time.monotonic()
        logger = structlog.get_logger("atrium")
        logger.info("handoff.stream_opened", stream="handoff", handoff_id=str(self._handoff_id))
        try:
            # 1.
            record, position = await self._touch_and_read()
            if record is None:
                yield _error("not_found", HANDOFF_NOT_FOUND)
                return
            yield format_event(
                "ready",
                {
                    "handoff_id": str(record.id),
                    "status": record.status,
                    "queue_position": position,
                    "seq": record.last_seq,
                },
            )
            self._last_status = (record.status, position, record.close_reason)
            for chunk in await self._new_messages():
                yield chunk
            if record.status == HandoffStatus.CLOSED:
                return
            next_tick = started + STREAM_TICK_SECONDS
            while True:
                # 4.
                now = time.monotonic()
                if now - started >= STREAM_MAX_SECONDS:
                    yield format_event("reconnect", {})
                    return
                timeout = max(0.0, min(next_tick, started + STREAM_MAX_SECONDS) - now)
                # 2.
                item = await next_stream_item(queue, disconnected, interval_seconds=timeout)
                if item is DISCONNECTED:
                    return
                if item is KEEPALIVE:
                    if time.monotonic() - started >= STREAM_MAX_SECONDS:
                        continue
                    next_tick = time.monotonic() + STREAM_TICK_SECONDS
                    if not await self._still_allowed():
                        yield _error("unauthenticated", STREAM_REVOKED)
                        return
                    yield format_comment(KEEPALIVE_COMMENT)
                    record, position = await self._touch_and_read()
                elif isinstance(item, HandoffNotice):
                    if item.handoff_id != self._handoff_id and item.kind not in ("queue", "status"):
                        continue
                    record, position = await self._read()
                else:
                    continue
                if record is None:
                    yield _error("not_found", HANDOFF_NOT_FOUND)
                    return
                for chunk in await self._new_messages():
                    yield chunk
                # 3.
                state = (record.status, position, record.close_reason)
                if state != self._last_status:
                    self._last_status = state
                    yield format_event(
                        "status",
                        {
                            "status": record.status,
                            "queue_position": position,
                            "close_reason": record.close_reason,
                        },
                    )
                if record.status == HandoffStatus.CLOSED:
                    return
        finally:
            self._service._broker.unsubscribe(queue)
            self._lease.release()
            logger.info(
                "handoff.stream_closed",
                stream="handoff",
                handoff_id=str(self._handoff_id),
                duration_ms=int((time.monotonic() - started) * 1000),
            )

    async def _touch_and_read(self) -> tuple[HandoffRecord | None, int | None]:
        """Grava `visitor_seen_at` e lê o atendimento com a posição, numa transação."""
        service = self._service
        async with open_session(service._database_url) as session, UnitOfWork(session):
            handoffs = HandoffRepository(session)
            await handoffs.touch_visitor(self._handoff_id, service._clock.now())
            return await _state(handoffs, self._handoff_id)

    async def _read(self) -> tuple[HandoffRecord | None, int | None]:
        """Lê o atendimento e a posição na fila, sem gravar nada."""
        async with open_session(self._service._database_url) as session, UnitOfWork(session):
            return await _state(HandoffRepository(session), self._handoff_id)

    async def _new_messages(self) -> list[str]:
        """As mensagens com `seq` maior que o último enviado, já como eventos `message`."""
        async with open_session(self._service._database_url) as session, UnitOfWork(session):
            rows = await HandoffRepository(session).messages_after(self._handoff_id, self._sent_seq)
        chunks = []
        for row in rows:
            self._sent_seq = max(self._sent_seq, row.seq)
            chunks.append(
                format_event(
                    "message",
                    message_payload(row),
                    event_id=message_event_id(row.handoff_id, row.seq),
                )
            )
        return chunks

    async def _still_allowed(self) -> bool:
        """A sessão ou a chave ainda valem e a conversa ainda é do visitante (seção 29.6)."""
        service = self._service
        try:
            visitor = await service._visitor(self._session_secret, self._guest_secret)
            async with open_session(service._database_url) as session, UnitOfWork(session):
                await service._owned_conversation(session, visitor, self._conversation_id)
        except DomainError:
            return False
        return True


def message_payload(row: HandoffMessageRecord) -> dict[str, object]:
    """A carga do evento `message` e da resposta das rotas de mensagem (seção 29.6).

    `role` é `user` ou `attendant`. Nunca leva quem da equipe escreveu.
    """
    return {
        "id": str(row.id),
        "seq": row.seq,
        "role": row.role,
        "content": row.content,
        "redaction": row.redaction,
        "created_at": row.created_at.isoformat(),
    }


async def _state(
    handoffs: HandoffRepository, handoff_id: UUID
) -> tuple[HandoffRecord | None, int | None]:
    """O atendimento e a posição na fila, quando está na fila."""
    record = await handoffs.get(handoff_id)
    if record is None or record.status != HandoffStatus.QUEUED:
        return record, None
    return record, queue_position(await handoffs.queue_ahead(record))


def count_close(record: HandoffRecord) -> None:
    """Conta o encerramento e registra o log, com o motivo e a duração, sem conteúdo.

    Serve ao visitante, à equipe e à varredura (seção 29.12).
    """
    reason = record.close_reason or "unknown"
    HANDOFF_CLOSED.labels(close_reason=reason).inc()
    duration_ms = 0
    if record.closed_at is not None:
        duration_ms = int((record.closed_at - record.requested_at).total_seconds() * 1000)
    with traced_span("handoff.close", close_reason=reason, duration_ms=duration_ms):
        pass
    structlog.get_logger("atrium").info(
        "handoff.closed",
        handoff_id=str(record.id),
        close_reason=reason,
        duration_ms=duration_ms,
    )


def _error(code: str, message: str) -> str:
    """O evento `error` do fluxo, que fecha em seguida."""
    return format_event("error", {"code": code, "message": message})
