"""Atendimento humano pelo lado da equipe e do admin. Seções 29.3, 29.5, 29.6 e 29.9.4.

Camada de serviço. `controllers/attendance.py` e `controllers/admin_handoffs.py` montam o
`AttendanceService` por pedido (`core/container.py:get_attendance_service`), depois de a
dependência `require_staff` confirmar a sessão de um `attendant` ou de um `admin`. Usa
`HandoffRepository`, `ConversationRepository`, `AuditRepository`, `RateLimitRepository`,
`AuthSessionRepository` e `UserRepository`, as regras de `domain/handoff.py` e a porta
`RealtimeBroker`.

O conteúdo só abre para quem assumiu (`attendant_id` igual à pessoa); fora disso, 404, igual a
um id inexistente (NFR-18). A fila e o evento `queue` não têm conteúdo, nome, e-mail nem tipo
de visitante (seção 29.9.4). Cada ação grava o evento de auditoria na mesma transação, com o
motivo ou a categoria e nunca o conteúdo (seção 29.7).
"""

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import HANDOFF_MESSAGES, HANDOFF_WAIT
from app.core.sse import (
    DISCONNECTED,
    KEEPALIVE,
    KEEPALIVE_COMMENT,
    format_comment,
    format_event,
    message_event_id,
    next_stream_item,
)
from app.core.telemetry import traced_span
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.auth import (
    STAFF_ROLES,
    RateDecision,
    bucket_key,
    fixed_window_start,
    hash_session_secret,
    retry_after_seconds,
)
from app.domain.errors import (
    AcknowledgementRequired,
    AttendantAtCapacity,
    Conflict,
    DuplicateMessage,
    HandoffClosed,
    HandoffTaken,
    NotFound,
    RateLimited,
    ValidationFailed,
)
from app.domain.grounding import Citation
from app.domain.handoff import (
    ATTENDANT_CLOSE_REASONS,
    HANDOFF_WINDOW,
    MAX_STAFF_CHARS,
    PRESENCE_WINDOW,
    REDACT_CATEGORIES,
    STAFF_MESSAGE_LIMIT,
    STAFF_MESSAGE_PURPOSE,
    STREAM_MAX_SECONDS,
    STREAM_TICK_SECONDS,
    CloseReason,
    HandoffNotice,
    HandoffStatus,
    PresenceStatus,
    RedactionCategory,
    StaffMember,
    clean_message,
    handoff_label_code,
    has_capacity,
)
from app.domain.insights import clean_reason
from app.domain.legal import ATTENDANT_TERMS_VERSION
from app.ports.clock import Clock
from app.ports.realtime import RealtimeBroker
from app.prompts.handoff import (
    ACKNOWLEDGEMENT_REQUIRED,
    AT_CAPACITY,
    CLOSED,
    DUPLICATE,
    HANDOFF_NOT_FOUND,
    INVALID_CATEGORY,
    INVALID_REASON,
    INVALID_TEXT,
    LABEL_PREFIX,
    RATE_LIMITED,
    STREAM_REVOKED,
    TAKEN,
    VIEW_ACTIVE,
    VIEW_REASON_LENGTH,
    WRONG_TERMS_VERSION,
)
from app.prompts.qa import MEDICAL_ADVICE
from app.repositories.audit import AuditRepository
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.conversations import ConversationRepository
from app.repositories.handoffs import (
    HandoffMessageConflict,
    HandoffMessageRecord,
    HandoffRecord,
    HandoffRepository,
)
from app.repositories.rate_limits import RateLimitRepository
from app.repositories.users import UserRepository
from app.services.handoff import count_close, message_payload
from app.services.stream_limits import LIMITER, StreamLease

# O modelo de mensagem da ação Enviar orientação de emergência (seção 29.10).
MEDICAL_EMERGENCY_TEMPLATE = "medical_emergency"
# Os períodos da lista de encerrados do admin (seção 29.10).
CLOSED_PERIOD_DAYS = (7, 30)


@dataclass(frozen=True, slots=True)
class AttendanceMe:
    """`GET /v1/attendance/me`: a presença marcada e se o compromisso vigente foi aceito."""

    presence: str
    acknowledged: bool
    terms_version: str


@dataclass(frozen=True, slots=True)
class StaffHandoff:
    """Um atendimento como a equipe o vê na fila ou na aba, sem conteúdo (seção 29.9.4)."""

    id: UUID
    label: str
    status: str
    trigger: str
    requested_at: datetime
    queued_at: datetime
    assigned_at: datetime | None
    closed_at: datetime | None
    close_reason: str | None
    returned: bool
    visitor_present: bool
    last_seq: int
    content_purged: bool


@dataclass(frozen=True, slots=True)
class ConversationLine:
    """Uma mensagem da conversa com a IA, para quem assumiu: pergunta, resposta e fontes."""

    id: UUID
    role: str
    content: str
    citations: tuple[Citation, ...]
    outcome: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class HandoffDetail:
    """O atendimento e a conversa como na seção 29.9.4, para quem assumiu ou para o admin."""

    handoff: StaffHandoff
    conversation: tuple[ConversationLine, ...]
    messages: tuple[HandoffMessageRecord, ...]


@dataclass(frozen=True, slots=True)
class QueueView:
    """`GET /v1/attendance/queue`: a fila, os atendimentos da pessoa e a equipe presente."""

    queued: tuple[StaffHandoff, ...]
    mine: tuple[StaffHandoff, ...]
    available_attendants: int


@dataclass(frozen=True, slots=True)
class ClosedItem:
    """Uma linha da lista de encerrados do admin, sem conteúdo (seção 29.10)."""

    handoff: StaffHandoff
    message_count: int


class AttendanceService:
    """Casos de uso da equipe: presença, fila, assumir, responder, remover e encerrar.

    `pseudonym_key` gera o rótulo do atendimento; `hmac_key`, o balde das mensagens da
    equipe; `broker` entrega os avisos aos fluxos deste processo.
    """

    def __init__(
        self,
        *,
        database_url: str,
        clock: Clock,
        hmac_key: str,
        pseudonym_key: str,
        broker: RealtimeBroker,
    ) -> None:
        self._database_url = database_url
        self._clock = clock
        self._hmac_key = hmac_key
        self._pseudonym_key = pseudonym_key
        self._broker = broker

    async def me(self, staff: StaffMember) -> AttendanceMe:
        """A presença e o aceite do compromisso vigente (seção 29.10)."""
        async with open_session(self._database_url) as session, UnitOfWork(session):
            return await self._me(HandoffRepository(session), staff)

    async def acknowledge(self, staff: StaffMember, version: str) -> AttendanceMe:
        """Grava o aceite. Uma versão que não é a vigente responde 422 (seção 29.3)."""
        if version != ATTENDANT_TERMS_VERSION:
            raise ValidationFailed(
                WRONG_TERMS_VERSION, field_errors={"version": WRONG_TERMS_VERSION}
            )
        async with open_session(self._database_url) as session, UnitOfWork(session):
            handoffs = HandoffRepository(session)
            await handoffs.acknowledge(staff.user_id, version, self._clock.now())
            return await self._me(handoffs, staff)

    async def set_presence(self, staff: StaffMember, status: str) -> AttendanceMe:
        """Marca Disponível ou Ausente, já com o sinal de agora. Avisa a fila."""
        value = PresenceStatus(status)
        async with open_session(self._database_url) as session, UnitOfWork(session):
            handoffs = HandoffRepository(session)
            await handoffs.set_presence(staff.user_id, value.value, self._clock.now())
            me = await self._me(handoffs, staff)
        return me

    async def queue(self, staff: StaffMember) -> QueueView:
        """A fila sem conteúdo, os atendimentos da pessoa e quantas pessoas estão presentes."""
        async with open_session(self._database_url) as session, UnitOfWork(session):
            return await self._queue(HandoffRepository(session), staff)

    async def take(self, staff: StaffMember, handoff_id: UUID) -> HandoffDetail:
        """Assume um atendimento da fila (seção 29.5, passo 4). FR-22.

        1. Exige o aceite do compromisso vigente (403 `acknowledgement_required`).
        2. Trava a pessoa e confere a capacidade de 3 (409 `attendant_at_capacity`).
        3. `UPDATE` condicional `WHERE status = 'queued'`: quem perde a corrida recebe 409
           `handoff_taken`. Assumir de novo o próprio atendimento devolve o mesmo.
        4. Grava `handoff.take` na mesma transação e o sinal de presença.
        5. Depois do commit, entrega o aviso e mede a espera na fila.
        """
        now = self._clock.now()
        notices: list[HandoffNotice] = []
        with traced_span("handoff.take") as span:
            async with open_session(self._database_url) as session, UnitOfWork(session):
                handoffs = HandoffRepository(session)
                # 1.
                if not await handoffs.has_acknowledged(staff.user_id, ATTENDANT_TERMS_VERSION):
                    raise AcknowledgementRequired(ACKNOWLEDGEMENT_REQUIRED)
                current = await handoffs.get(handoff_id)
                if current is None:
                    raise NotFound(HANDOFF_NOT_FOUND)
                mine = current.attendant_id == staff.user_id
                if current.status == HandoffStatus.ASSIGNED and mine:
                    return await self._detail(session, handoffs, current)
                if current.status == HandoffStatus.CLOSED:
                    raise HandoffClosed(CLOSED)
                if current.status == HandoffStatus.ASSIGNED:
                    raise HandoffTaken(TAKEN)
                # 2.
                await handoffs.lock_key(staff.user_id)
                if not has_capacity(len(await handoffs.assigned_to(staff.user_id))):
                    raise AttendantAtCapacity(AT_CAPACITY)
                # 3.
                taken = await handoffs.take(handoff_id, staff.user_id, now)
                if taken is None:
                    raise HandoffTaken(TAKEN)
                # 4.
                await AuditRepository(session).record(
                    actor_user_id=staff.user_id,
                    action="handoff.take",
                    target_type="handoff",
                    target_id=handoff_id,
                    created_at=now,
                )
                await handoffs.touch_presence(staff.user_id, now)
                notices = list(handoffs.notices)
                detail = await self._detail(session, handoffs, taken)
            wait = max(0.0, (now - taken.queued_at).total_seconds())
            span.set(wait_ms=int(wait * 1000))
        # 5.
        await self._broker.committed(notices)
        HANDOFF_WAIT.observe(wait)
        structlog.get_logger("atrium").info(
            "handoff.assigned",
            handoff_id=str(handoff_id),
            label=detail.handoff.label,
            wait_ms=int(wait * 1000),
        )
        return detail

    async def detail(
        self, staff: StaffMember, handoff_id: UUID, *, after_seq: int | None = None
    ) -> HandoffDetail:
        """O atendimento e a conversa, só para quem assumiu (404 para outra pessoa).

        Com `after_seq`, traz só as mensagens do atendimento com `seq` maior, para a
        retomada do console (seção 29.6).
        """
        async with open_session(self._database_url) as session, UnitOfWork(session):
            handoffs = HandoffRepository(session)
            record = await self._mine(handoffs, staff, handoff_id, allow_closed=True)
            return await self._detail(session, handoffs, record, after_seq=after_seq)

    async def send(
        self,
        staff: StaffMember,
        handoff_id: UUID,
        *,
        text: str | None,
        template: str | None,
        client_message_id: UUID,
    ) -> HandoffMessageRecord:
        """Grava a resposta da equipe, sem passar pela remoção de identificadores (29.5).

        O modelo `medical_emergency` manda o texto fixo de orientação médica da seção 10.1.
        Conta no balde de 600 por hora por pessoa. Atendimento encerrado, 409; de outra
        pessoa, 404; reenvio do mesmo `client_message_id`, 409 com `message_id`.
        """
        if template == MEDICAL_EMERGENCY_TEMPLATE:
            body = MEDICAL_ADVICE
        elif template is not None or text is None:
            raise ValidationFailed(INVALID_TEXT.format(max_chars=MAX_STAFF_CHARS))
        else:
            cleaned = clean_message(text, MAX_STAFF_CHARS)
            if cleaned is None:
                raise ValidationFailed(INVALID_TEXT.format(max_chars=MAX_STAFF_CHARS))
            body = cleaned
        self._require_hmac()
        now = self._clock.now()
        limited: RateDecision | None = None
        stored: HandoffMessageRecord | None = None
        notices: list[HandoffNotice] = []
        with traced_span("handoff.message", role="attendant", redaction_count=0):
            try:
                async with open_session(self._database_url) as session, UnitOfWork(session):
                    handoffs = HandoffRepository(session)
                    record = await self._mine(handoffs, staff, handoff_id, allow_closed=True)
                    if record.status == HandoffStatus.CLOSED:
                        raise HandoffClosed(CLOSED)
                    decision = await self._consume(session, staff.user_id, now)
                    if decision.limited:
                        limited = decision
                    else:
                        stored = await handoffs.append_message(
                            handoff_id=handoff_id,
                            conversation_id=record.conversation_id,
                            role="attendant",
                            content=body,
                            client_message_id=client_message_id,
                            author_user_id=staff.user_id,
                            now=now,
                            attendant_id=staff.user_id,
                        )
                        await handoffs.touch_presence(staff.user_id, now)
                        notices = list(handoffs.notices)
            except HandoffMessageConflict as exc:
                raise DuplicateMessage(DUPLICATE, message_id=exc.message_id) from None
        if limited is not None:
            raise RateLimited(RATE_LIMITED, retry_after_seconds=limited.retry_after_seconds)
        if stored is None:
            raise HandoffClosed(CLOSED)
        await self._broker.committed(notices)
        HANDOFF_MESSAGES.labels(role="attendant").inc()
        return stored

    async def release(self, staff: StaffMember, handoff_id: UUID) -> StaffHandoff:
        """Devolve à fila (seção 29.5, passo 6) e grava `handoff.release`."""
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            handoffs = HandoffRepository(session)
            record = await self._mine(handoffs, staff, handoff_id, allow_closed=True)
            if record.status == HandoffStatus.CLOSED:
                raise HandoffClosed(CLOSED)
            released = await handoffs.release(handoff_id, staff.user_id, now)
            if released is None:
                raise NotFound(HANDOFF_NOT_FOUND)
            await AuditRepository(session).record(
                actor_user_id=staff.user_id,
                action="handoff.release",
                target_type="handoff",
                target_id=handoff_id,
                created_at=now,
            )
            notices = list(handoffs.notices)
            view = self._staff_view(released, now)
        await self._broker.committed(notices)
        structlog.get_logger("atrium").info("handoff.released", handoff_id=str(handoff_id))
        return view

    async def close(self, staff: StaffMember, handoff_id: UUID, reason: str) -> StaffHandoff:
        """Encerra com um motivo da lista fechada (FR-24) e grava `handoff.close`."""
        if reason not in ATTENDANT_CLOSE_REASONS:
            raise ValidationFailed(INVALID_REASON, field_errors={"reason": INVALID_REASON})
        close_reason = CloseReason(reason)
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            handoffs = HandoffRepository(session)
            record = await self._mine(handoffs, staff, handoff_id, allow_closed=True)
            if record.status == HandoffStatus.CLOSED:
                raise HandoffClosed(CLOSED)
            closed = await handoffs.close(
                handoff_id, reason=close_reason, now=now, attendant_id=staff.user_id
            )
            if closed is None:
                raise NotFound(HANDOFF_NOT_FOUND)
            await AuditRepository(session).record(
                actor_user_id=staff.user_id,
                action="handoff.close",
                target_type="handoff",
                target_id=handoff_id,
                created_at=now,
                reason=close_reason.value,
            )
            notices = list(handoffs.notices)
            view = self._staff_view(closed, now)
        await self._broker.committed(notices)
        count_close(closed)
        return view

    async def redact(
        self, staff: StaffMember, handoff_id: UUID, message_id: UUID, category: str
    ) -> HandoffMessageRecord:
        """Troca o texto de uma mensagem do atendimento pelo marcador (seção 29.9.6). FR-25.

        Apaga o original na mesma transação, sem cópia, e grava `handoff.message_redact` só
        com a categoria. A mensagem ganha um `seq` novo e volta ao fluxo do visitante.
        """
        if category not in REDACT_CATEGORIES:
            raise ValidationFailed(INVALID_CATEGORY, field_errors={"category": INVALID_CATEGORY})
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            handoffs = HandoffRepository(session)
            record = await self._mine(handoffs, staff, handoff_id, allow_closed=True)
            if record.status == HandoffStatus.CLOSED:
                raise HandoffClosed(CLOSED)
            redacted = await handoffs.redact_message(
                handoff_id=handoff_id,
                message_id=message_id,
                attendant_id=staff.user_id,
                category=RedactionCategory(category).value,
                now=now,
            )
            if redacted is None:
                raise NotFound(HANDOFF_NOT_FOUND)
            await AuditRepository(session).record(
                actor_user_id=staff.user_id,
                action="handoff.message_redact",
                target_type="handoff",
                target_id=handoff_id,
                created_at=now,
                reason=category,
            )
            notices = list(handoffs.notices)
        await self._broker.committed(notices)
        structlog.get_logger("atrium").info(
            "handoff.redacted", handoff_id=str(handoff_id), category=category
        )
        return redacted

    async def closed_list(self, period_days: int) -> list[ClosedItem]:
        """Até 100 encerrados no período, do mais recente ao mais antigo, sem conteúdo."""
        if period_days not in CLOSED_PERIOD_DAYS:
            raise ValidationFailed(INVALID_REASON, field_errors={"period_days": INVALID_REASON})
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            rows = await HandoffRepository(session).closed_since(now - timedelta(days=period_days))
        return [
            ClosedItem(handoff=self._staff_view(row.record, now), message_count=row.message_count)
            for row in rows
        ]

    async def view_closed(self, admin: StaffMember, handoff_id: UUID, reason: str) -> HandoffDetail:
        """O admin lê um encerrado com motivo, gravado em `handoff.view` (FR-26).

        Sem motivo de 10 a 500 caracteres, 422 em `field_errors.reason`, sem gravar nada.
        Atendimento ativo, 409.
        """
        cleaned = clean_reason(reason)
        if cleaned is None:
            raise ValidationFailed(VIEW_REASON_LENGTH, field_errors={"reason": VIEW_REASON_LENGTH})
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            handoffs = HandoffRepository(session)
            record = await handoffs.get(handoff_id)
            if record is None:
                raise NotFound(HANDOFF_NOT_FOUND)
            if record.status != HandoffStatus.CLOSED:
                raise Conflict(VIEW_ACTIVE)
            await AuditRepository(session).record(
                actor_user_id=admin.user_id,
                action="handoff.view",
                target_type="handoff",
                target_id=handoff_id,
                created_at=now,
                reason=cleaned,
            )
            return await self._detail(session, handoffs, record)

    async def open_console(self, staff: StaffMember, session_secret: str | None) -> "ConsoleStream":
        """A vaga do fluxo do console, 2 por pessoa e 300 no processo (429 acima)."""
        lease = LIMITER.acquire("attendance", str(staff.user_id))
        return ConsoleStream(service=self, staff=staff, session_secret=session_secret, lease=lease)

    async def _me(self, handoffs: HandoffRepository, staff: StaffMember) -> AttendanceMe:
        """A presença marcada, `away` sem linha, e o aceite da versão vigente."""
        presence = await handoffs.presence(staff.user_id)
        return AttendanceMe(
            presence=PresenceStatus.AWAY.value if presence is None else presence[0],
            acknowledged=await handoffs.has_acknowledged(staff.user_id, ATTENDANT_TERMS_VERSION),
            terms_version=ATTENDANT_TERMS_VERSION,
        )

    async def _queue(self, handoffs: HandoffRepository, staff: StaffMember) -> QueueView:
        """A fila e os atendimentos da pessoa, com o rótulo e sem conteúdo."""
        now = self._clock.now()
        return QueueView(
            queued=tuple(self._staff_view(row, now) for row in await handoffs.queued()),
            mine=tuple(
                self._staff_view(row, now) for row in await handoffs.assigned_to(staff.user_id)
            ),
            available_attendants=await handoffs.count_present_staff(now),
        )

    async def _mine(
        self,
        handoffs: HandoffRepository,
        staff: StaffMember,
        handoff_id: UUID,
        *,
        allow_closed: bool,
    ) -> HandoffRecord:
        """O atendimento de quem pede. Para outra pessoa, ou na fila, o mesmo 404 (NFR-18).

        Um atendimento encerrado continua da pessoa que o tinha, para o 409 de
        `handoff_closed`; devolvido à fila, ele já não tem `attendant_id`.
        """
        record = await handoffs.get(handoff_id)
        if record is None or record.attendant_id != staff.user_id:
            raise NotFound(HANDOFF_NOT_FOUND)
        if record.status == HandoffStatus.CLOSED and not allow_closed:
            raise HandoffClosed(CLOSED)
        return record

    async def _detail(
        self,
        session: AsyncSession,
        handoffs: HandoffRepository,
        record: HandoffRecord,
        *,
        after_seq: int | None = None,
    ) -> HandoffDetail:
        """A conversa com a IA, sem outras conversas nem outros atendimentos, e as mensagens.

        A conversa com a IA vem só sem `after_seq`: a retomada do console traz só o que é
        novo no atendimento. A mensagem de saúde já está gravada como o marcador (29.9.4).
        """
        now = self._clock.now()
        lines: tuple[ConversationLine, ...] = ()
        if after_seq is None:
            rows = await ConversationRepository(session).list_messages(record.conversation_id)
            lines = tuple(
                ConversationLine(
                    id=row.id,
                    role=row.role,
                    content=row.content,
                    citations=row.citations,
                    outcome=row.outcome,
                    created_at=row.created_at,
                )
                for row in rows
                if row.handoff_id is None
            )
        messages = await handoffs.messages_after(record.id, after_seq or 0)
        return HandoffDetail(
            handoff=self._staff_view(record, now),
            conversation=lines,
            messages=tuple(messages),
        )

    def _staff_view(self, record: HandoffRecord, now: datetime) -> StaffHandoff:
        """O atendimento com o rótulo do HMAC do id e se o visitante está na conversa."""
        return StaffHandoff(
            id=record.id,
            label=self.label(record.id),
            status=record.status,
            trigger=record.trigger,
            requested_at=record.requested_at,
            queued_at=record.queued_at,
            assigned_at=record.assigned_at,
            closed_at=record.closed_at,
            close_reason=record.close_reason,
            returned=record.assigned_at is not None and record.status == HandoffStatus.QUEUED,
            visitor_present=now - record.visitor_seen_at <= PRESENCE_WINDOW,
            last_seq=record.last_seq,
            content_purged=record.content_purged_at is not None,
        )

    def label(self, handoff_id: UUID) -> str:
        """ "Visitante" e os 8 caracteres do HMAC do id do atendimento (seção 29.9.4)."""
        return f"{LABEL_PREFIX} {handoff_label_code(handoff_id, self._pseudonym_key)}"

    async def _consume(self, session: AsyncSession, user_id: UUID, now: datetime) -> RateDecision:
        """Conta a mensagem no balde de 600 por hora por pessoa da equipe (seção 29.8)."""
        window = fixed_window_start(now, HANDOFF_WINDOW)
        count = await RateLimitRepository(session).increment(
            bucket_key(
                purpose=STAFF_MESSAGE_PURPOSE,
                subject=str(user_id),
                day=now.astimezone(UTC).date(),
                key=self._hmac_key,
            ),
            window,
        )
        if count <= STAFF_MESSAGE_LIMIT:
            return RateDecision(limited=False, retry_after_seconds=0)
        return RateDecision(
            limited=True,
            retry_after_seconds=retry_after_seconds(now, window, HANDOFF_WINDOW),
        )

    async def _staff_still_valid(self, staff: StaffMember, session_secret: str | None) -> bool:
        """A sessão ainda vale e o papel ainda é da equipe, a cada tique (seção 29.6)."""
        if not session_secret:
            return False
        async with open_session(self._database_url) as session, UnitOfWork(session):
            found = await AuthSessionRepository(session).get_active(
                hash_session_secret(session_secret), self._clock.now()
            )
            if found is None or found.user_id != staff.user_id:
                return False
            user = await UserRepository(session).get_by_id(staff.user_id)
        return user is not None and user.role in STAFF_ROLES

    def _require_hmac(self) -> None:
        """Sem `RATE_LIMIT_HMAC_KEY` não há balde: falha como erro de servidor."""
        if not self._hmac_key:
            raise RuntimeError("RATE_LIMIT_HMAC_KEY vazio.")


class ConsoleStream:
    """O fluxo SSE do console de uma pessoa da equipe (seção 29.6).

    Mistura a fila, sem conteúdo, com as mensagens dos atendimentos que a pessoa assumiu. Na
    retomada, o console lê de novo a fila e cada atendimento aberto com `after_seq`, por isso
    este fluxo começa sem histórico: só manda o que muda depois do `ready`.
    """

    def __init__(
        self,
        *,
        service: AttendanceService,
        staff: StaffMember,
        session_secret: str | None,
        lease: StreamLease,
    ) -> None:
        self._service = service
        self._staff = staff
        self._session_secret = session_secret
        self._lease = lease
        # O último `seq` enviado e a presença do visitante, por atendimento da pessoa.
        self._sent: dict[UUID, int] = {}
        self._present: dict[UUID, bool] = {}
        self._last_queue: object = None

    async def events(self, disconnected: asyncio.Event) -> AsyncIterator[str]:
        """Os eventos do console, já em texto SSE.

        1. `ready` com a presença e o aceite, e a fila atual em `queue`.
        2. A cada aviso, lê de novo a fila e os atendimentos da pessoa.
        3. A cada tique, confere a sessão e o papel, grava o sinal de presença, lê de novo e
           manda `: keepalive`.
        4. Aos 10 minutos, `reconnect`, e o fluxo fecha.
        """
        service = self._service
        queue = service._broker.subscribe()
        started = time.monotonic()
        logger = structlog.get_logger("atrium")
        logger.info("handoff.stream_opened", stream="attendance")
        try:
            # 1.
            async with open_session(service._database_url) as session, UnitOfWork(session):
                handoffs = HandoffRepository(session)
                await handoffs.touch_presence(self._staff.user_id, service._clock.now())
                me = await service._me(handoffs, self._staff)
                for record in await handoffs.assigned_to(self._staff.user_id):
                    self._sent[record.id] = record.last_seq
                    self._present[record.id] = self._is_present(record)
            yield format_event("ready", {"presence": me.presence, "acknowledged": me.acknowledged})
            for chunk in await self._refresh():
                yield chunk
            next_tick = started + STREAM_TICK_SECONDS
            while True:
                now = time.monotonic()
                # 4.
                if now - started >= STREAM_MAX_SECONDS:
                    yield format_event("reconnect", {})
                    return
                timeout = max(0.0, min(next_tick, started + STREAM_MAX_SECONDS) - now)
                item = await next_stream_item(queue, disconnected, interval_seconds=timeout)
                if item is DISCONNECTED:
                    return
                if item is KEEPALIVE:
                    if time.monotonic() - started >= STREAM_MAX_SECONDS:
                        continue
                    # 3.
                    next_tick = time.monotonic() + STREAM_TICK_SECONDS
                    if not await service._staff_still_valid(self._staff, self._session_secret):
                        yield format_event(
                            "error", {"code": "unauthenticated", "message": STREAM_REVOKED}
                        )
                        return
                    async with open_session(service._database_url) as session, UnitOfWork(session):
                        await HandoffRepository(session).touch_presence(
                            self._staff.user_id, service._clock.now()
                        )
                    yield format_comment(KEEPALIVE_COMMENT)
                elif not isinstance(item, HandoffNotice):
                    continue
                # 2.
                for chunk in await self._refresh():
                    yield chunk
        finally:
            service._broker.unsubscribe(queue)
            self._lease.release()
            logger.info(
                "handoff.stream_closed",
                stream="attendance",
                duration_ms=int((time.monotonic() - started) * 1000),
            )

    async def _refresh(self) -> list[str]:
        """Lê a fila e os atendimentos da pessoa e devolve os eventos do que mudou."""
        service = self._service
        chunks: list[str] = []
        async with open_session(service._database_url) as session, UnitOfWork(session):
            handoffs = HandoffRepository(session)
            view = await service._queue(handoffs, self._staff)
            mine = {row.id: row for row in await handoffs.assigned_to(self._staff.user_id)}
            # Os atendimentos que saíram da pessoa: encerrados, devolvidos ou apagados.
            gone: dict[UUID, HandoffRecord | None] = {}
            for handoff_id in [key for key in self._sent if key not in mine]:
                gone[handoff_id] = await handoffs.get(handoff_id)
            fresh: dict[UUID, list[HandoffMessageRecord]] = {}
            for handoff_id in mine:
                fresh[handoff_id] = await handoffs.messages_after(
                    handoff_id, self._sent.get(handoff_id, 0)
                )
        snapshot = [queue_item_payload(item) for item in view.queued]
        state = (snapshot, view.available_attendants)
        if state != self._last_queue:
            self._last_queue = state
            chunks.append(
                format_event(
                    "queue",
                    {"queued": snapshot, "available_attendants": view.available_attendants},
                )
            )
        for handoff_id, record in gone.items():
            del self._sent[handoff_id]
            self._present.pop(handoff_id, None)
            if record is not None and record.status == HandoffStatus.CLOSED:
                chunks.append(
                    format_event(
                        "status",
                        {
                            "handoff_id": str(handoff_id),
                            "status": record.status,
                            "close_reason": record.close_reason,
                            "visitor_present": self._is_present(record),
                        },
                    )
                )
            else:
                chunks.append(format_event("removed", {"handoff_id": str(handoff_id)}))
        for handoff_id, record in mine.items():
            if handoff_id not in self._sent:
                # Assumido em outra aba: o console lê o atendimento pelo `GET`.
                self._sent[handoff_id] = record.last_seq
                self._present[handoff_id] = self._is_present(record)
                chunks.append(format_event("assigned", {"handoff_id": str(handoff_id)}))
                continue
            for row in fresh.get(handoff_id, []):
                if row.seq <= self._sent[handoff_id]:
                    continue
                self._sent[handoff_id] = row.seq
                payload = {"handoff_id": str(handoff_id), **message_payload(row)}
                chunks.append(
                    format_event("message", payload, event_id=message_event_id(handoff_id, row.seq))
                )
            present = self._is_present(record)
            if present != self._present.get(handoff_id):
                self._present[handoff_id] = present
                chunks.append(
                    format_event(
                        "status",
                        {
                            "handoff_id": str(handoff_id),
                            "status": record.status,
                            "close_reason": record.close_reason,
                            "visitor_present": present,
                        },
                    )
                )
        return chunks

    def _is_present(self, record: HandoffRecord) -> bool:
        """O visitante está na conversa: o fluxo dele mandou sinal nos últimos 45 segundos."""
        return self._service._clock.now() - record.visitor_seen_at <= PRESENCE_WINDOW


def queue_item_payload(item: StaffHandoff) -> dict[str, object]:
    """Um item do evento `queue`, sem conteúdo nem dado do perfil (seção 29.9.4)."""
    return {
        "handoff_id": str(item.id),
        "label": item.label,
        "requested_at": item.requested_at.isoformat(),
        "queued_at": item.queued_at.isoformat(),
        "trigger": item.trigger,
        "returned": item.returned,
        "visitor_present": item.visitor_present,
    }
