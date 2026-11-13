"""Atendimentos, mensagens do atendimento, presença e aceite da equipe. Seção 29.7 do SDD.

Camada de repositório (seção 6.2). Lê e grava `handoffs`, as mensagens com `handoff_id`,
`attendant_presence` e `attendant_acknowledgements`. Quem usa: `HandoffService` (o visitante),
`AttendanceService` (a equipe e o admin), `HandoffSweeper` (a varredura), `ConversationService`
(o 409 da pergunta durante o atendimento), o script `attendants` e as métricas lidas do banco.

Toda gravação que muda um atendimento chama `pg_notify('atrium_handoff', carga)` na mesma
transação (ADR-016): o PostgreSQL entrega o aviso só depois do commit. A carga tem só o id, o
`seq` e o tipo. Os avisos também ficam em `notices`, para o serviço chamar
`RealtimeBroker.committed` depois do commit. As transições de status são `UPDATE`
condicionais (`WHERE status = ...`): quem perde uma corrida recebe `None`, e duas varreduras
ao mesmo tempo não duplicam efeito (seção 29.5).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import ColumnElement, Select, and_, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.handoff import (
    ASSIGNED_IDLE,
    ATTENDANT_GONE,
    PRESENCE_WINDOW,
    QUEUE_TIMEOUT,
    REDACTED_MARKER,
    VISITOR_ABSENT,
    CloseReason,
    HandoffNotice,
    HandoffStatus,
    NoticeKind,
    PresenceStatus,
    notify_payload,
)
from app.models.attendant_acknowledgement import AttendantAcknowledgement
from app.models.attendant_presence import AttendantPresence
from app.models.conversation import Conversation
from app.models.feedback import Feedback
from app.models.handoff import Handoff
from app.models.message import Message
from app.models.user import User

# Papéis que atendem: a pessoa da equipe e o admin (seção 29.3).
_STAFF_ROLES = ("attendant", "admin")


@dataclass(frozen=True, slots=True)
class HandoffRecord:
    """Uma cópia imutável da linha de `handoffs`, desligada da sessão."""

    id: UUID
    conversation_id: UUID
    status: str
    trigger: str
    trigger_message_id: UUID | None
    attendant_id: UUID | None
    close_reason: str | None
    requested_at: datetime
    queued_at: datetime
    assigned_at: datetime | None
    closed_at: datetime | None
    last_activity_at: datetime
    visitor_seen_at: datetime
    last_seq: int
    content_purged_at: datetime | None
    # `web` ou `whatsapp`, copiado da conversa no pedido (seção 30.7).
    channel: str = "web"


@dataclass(frozen=True, slots=True)
class HandoffMessageRecord:
    """Uma mensagem do atendimento, com o `seq` da retomada (seção 29.6)."""

    id: UUID
    handoff_id: UUID
    seq: int
    role: str
    content: str
    redaction: str | None
    client_message_id: UUID | None
    author_user_id: UUID | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class LastAnswer:
    """A última resposta do assistente fora do atendimento, para a regra da oferta."""

    message_id: UUID
    outcome: str | None
    rated_not_helpful: bool


@dataclass(frozen=True, slots=True)
class ClosedHandoff:
    """Um atendimento encerrado para a lista do admin, sem conteúdo (seção 29.10)."""

    record: HandoffRecord
    message_count: int


class HandoffMessageConflict(Exception):
    """O `client_message_id` já está gravado na conversa. Guarda o id da mensagem gravada."""

    def __init__(self, message_id: UUID) -> None:
        super().__init__("duplicate handoff message")
        self.message_id = message_id


class HandoffRepository:
    """Consultas e gravações do atendimento humano, na transação do serviço."""

    def __init__(self, session: AsyncSession) -> None:
        """Usa a sessão aberta pelo serviço, sem abrir transação própria."""
        self._session = session
        # Os avisos feitos nesta transação, na ordem, para o `RealtimeBroker.committed`.
        self.notices: list[HandoffNotice] = []

    async def notify(self, handoff_id: UUID, seq: int, kind: NoticeKind) -> None:
        """`pg_notify` na transação atual e o aviso guardado em `notices` (ADR-016)."""
        await self._session.execute(
            text("SELECT pg_notify(:channel, :payload)"),
            {"channel": "atrium_handoff", "payload": notify_payload(handoff_id, seq, kind)},
        )
        self.notices.append(HandoffNotice(handoff_id=handoff_id, seq=seq, kind=kind))

    async def lock_key(self, key: UUID) -> None:
        """Trava, até o fim da transação, tudo que usa a mesma chave.

        Serve ao pedido de um mesmo visitante e ao assumir de uma mesma pessoa: dois pedidos
        ao mesmo tempo não passam juntos pela regra de um atendimento ativo, nem pela
        capacidade de 3. `hashtextextended` dá um inteiro de 64 bits estável para o UUID.
        """
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"handoff:{key}"},
        )

    async def get(self, handoff_id: UUID) -> HandoffRecord | None:
        """O atendimento pela chave primária, lido do banco, sem o mapa de identidade."""
        row = await self._session.scalar(
            select(Handoff)
            .where(Handoff.id == handoff_id)
            .execution_options(populate_existing=True)
        )
        return None if row is None else _record(row)

    async def active_for_conversation(self, conversation_id: UUID) -> HandoffRecord | None:
        """O atendimento ativo da conversa, pelo índice único parcial."""
        row = await self._session.scalar(
            select(Handoff)
            .where(Handoff.conversation_id == conversation_id, Handoff.status != "closed")
            .execution_options(populate_existing=True)
        )
        return None if row is None else _record(row)

    async def latest_for_conversation(self, conversation_id: UUID) -> HandoffRecord | None:
        """O atendimento ativo ou, sem ele, o último da conversa."""
        active = await self.active_for_conversation(conversation_id)
        if active is not None:
            return active
        row = await self._session.scalar(
            select(Handoff)
            .where(Handoff.conversation_id == conversation_id)
            .order_by(Handoff.requested_at.desc(), Handoff.id.desc())
            .limit(1)
        )
        return None if row is None else _record(row)

    async def list_for_conversation(self, conversation_id: UUID) -> list[HandoffRecord]:
        """Todos os atendimentos da conversa, do mais antigo ao mais novo."""
        rows = await self._session.scalars(
            select(Handoff)
            .where(Handoff.conversation_id == conversation_id)
            .order_by(Handoff.requested_at.asc(), Handoff.id.asc())
        )
        return [_record(row) for row in rows]

    async def active_for_subject(
        self, *, user_id: UUID | None, guest_key_id: UUID | None
    ) -> HandoffRecord | None:
        """Um atendimento ativo do mesmo visitante, em qualquer conversa (seção 29.4)."""
        row = await self._session.scalar(
            _subject_handoffs(user_id, guest_key_id).where(Handoff.status != "closed").limit(1)
        )
        return None if row is None else _record(row)

    async def last_abusive_close(
        self, *, user_id: UUID | None, guest_key_id: UUID | None
    ) -> datetime | None:
        """O encerramento `abusive` mais recente do visitante, para o bloqueio de 24 horas."""
        row = await self._session.scalar(
            _subject_handoffs(user_id, guest_key_id)
            .where(Handoff.close_reason == CloseReason.ABUSIVE)
            .order_by(Handoff.closed_at.desc())
            .limit(1)
        )
        return None if row is None else row.closed_at

    async def last_answer(self, conversation_id: UUID) -> LastAnswer | None:
        """A última resposta do assistente, fora do atendimento, com a nota não útil."""
        row = (
            await self._session.execute(
                select(Message.id, Message.outcome, Feedback.rating)
                .outerjoin(Feedback, Feedback.message_id == Message.id)
                .where(
                    Message.conversation_id == conversation_id,
                    Message.role == "assistant",
                    Message.handoff_id.is_(None),
                )
                .order_by(Message.created_at.desc(), Message.id.desc())
                .limit(1)
            )
        ).first()
        if row is None:
            return None
        message_id, outcome, rating = row
        return LastAnswer(message_id=message_id, outcome=outcome, rated_not_helpful=rating == -1)

    async def count_queued(self) -> int:
        """Quantos atendimentos estão na fila, para a disponibilidade e a métrica."""
        value = await self._session.scalar(
            select(func.count()).select_from(Handoff).where(Handoff.status == "queued")
        )
        return int(value or 0)

    async def count_present_staff(self, now: datetime) -> int:
        """Quantas pessoas da equipe estão presentes: `available` com sinal em 45 s."""
        value = await self._session.scalar(
            select(func.count())
            .select_from(AttendantPresence)
            .join(User, User.id == AttendantPresence.user_id)
            .where(
                AttendantPresence.status == PresenceStatus.AVAILABLE,
                AttendantPresence.last_seen_at >= now - PRESENCE_WINDOW,
                User.role.in_(_STAFF_ROLES),
            )
        )
        return int(value or 0)

    async def queue_ahead(self, handoff: HandoffRecord) -> int:
        """Quantos atendimentos na fila foram pedidos antes deste. O `id` desempata."""
        value = await self._session.scalar(
            select(func.count())
            .select_from(Handoff)
            .where(
                Handoff.status == "queued",
                or_(
                    Handoff.requested_at < handoff.requested_at,
                    and_(
                        Handoff.requested_at == handoff.requested_at,
                        Handoff.id < handoff.id,
                    ),
                ),
            )
        )
        return int(value or 0)

    async def queued(self) -> list[HandoffRecord]:
        """A fila pela ordem de `requested_at` (seção 29.5)."""
        rows = await self._session.scalars(
            select(Handoff)
            .where(Handoff.status == "queued")
            .order_by(Handoff.requested_at.asc(), Handoff.id.asc())
        )
        return [_record(row) for row in rows]

    async def assigned_to(self, attendant_id: UUID) -> list[HandoffRecord]:
        """Os atendimentos `assigned` da pessoa, do mais antigo ao mais novo."""
        rows = await self._session.scalars(
            select(Handoff)
            .where(Handoff.status == "assigned", Handoff.attendant_id == attendant_id)
            .order_by(Handoff.assigned_at.asc(), Handoff.id.asc())
            .execution_options(populate_existing=True)
        )
        return [_record(row) for row in rows]

    async def insert(
        self,
        *,
        conversation_id: UUID,
        trigger: str,
        trigger_message_id: UUID | None,
        now: datetime,
    ) -> HandoffRecord:
        """Grava o atendimento `queued` e avisa a fila. O `flush()` traz o id gerado.

        O canal vem da conversa: `whatsapp` faz o console mostrar o selo (seção 30.5).
        """
        channel = await self._session.scalar(
            select(Conversation.channel).where(Conversation.id == conversation_id)
        )
        row = Handoff(
            conversation_id=conversation_id,
            channel=channel or "web",
            status=HandoffStatus.QUEUED.value,
            trigger=trigger,
            trigger_message_id=trigger_message_id,
            requested_at=now,
            queued_at=now,
            last_activity_at=now,
            visitor_seen_at=now,
            last_seq=0,
        )
        self._session.add(row)
        await self._session.flush()
        record = _record(row)
        await self.notify(record.id, record.last_seq, NoticeKind.QUEUE)
        return record

    async def take(
        self, handoff_id: UUID, attendant_id: UUID, now: datetime
    ) -> HandoffRecord | None:
        """Assume pelo `UPDATE` condicional `WHERE status = 'queued'` (seção 29.5).

        Devolve `None` quando outra pessoa assumiu primeiro ou o atendimento saiu da fila.
        """
        record = await self._transition(
            (Handoff.id == handoff_id, Handoff.status == "queued"),
            {
                "status": HandoffStatus.ASSIGNED.value,
                "attendant_id": attendant_id,
                "assigned_at": now,
                "last_activity_at": now,
            },
        )
        if record is not None:
            await self.notify(record.id, record.last_seq, NoticeKind.STATUS)
        return record

    async def release(
        self, handoff_id: UUID, attendant_id: UUID, now: datetime
    ) -> HandoffRecord | None:
        """Devolve à fila: `queued_at` recomeça e o `requested_at` original fica (29.5)."""
        record = await self._transition(
            (
                Handoff.id == handoff_id,
                Handoff.status == "assigned",
                Handoff.attendant_id == attendant_id,
            ),
            {"status": HandoffStatus.QUEUED.value, "attendant_id": None, "queued_at": now},
        )
        if record is not None:
            await self.notify(record.id, record.last_seq, NoticeKind.STATUS)
        return record

    async def close(
        self,
        handoff_id: UUID,
        *,
        reason: CloseReason,
        now: datetime,
        attendant_id: UUID | None = None,
    ) -> HandoffRecord | None:
        """Encerra um atendimento ativo. Com `attendant_id`, só o de quem assumiu."""
        conditions: list[ColumnElement[bool]] = [
            Handoff.id == handoff_id,
            Handoff.status != "closed",
        ]
        if attendant_id is not None:
            conditions += [Handoff.status == "assigned", Handoff.attendant_id == attendant_id]
        record = await self._transition(
            conditions,
            {
                "status": HandoffStatus.CLOSED.value,
                "close_reason": reason.value,
                "closed_at": now,
            },
        )
        if record is not None:
            await self.notify(record.id, record.last_seq, NoticeKind.STATUS)
        return record

    async def append_message(
        self,
        *,
        handoff_id: UUID,
        conversation_id: UUID,
        role: str,
        content: str,
        client_message_id: UUID,
        author_user_id: UUID | None,
        now: datetime,
        attendant_id: UUID | None = None,
    ) -> HandoffMessageRecord | None:
        """Grava a mensagem com o próximo `seq` e avisa os fluxos (seção 29.5, passo 5).

        1. Soma 1 em `last_seq` e atualiza `last_activity_at` com um `UPDATE` que trava a
           linha. Só um atendimento ativo muda; com `attendant_id`, só o de quem assumiu.
        2. Grava a mensagem com esse `seq`, depois da mensagem mais nova da conversa.
        3. `NOTIFY` com o tipo `message`.

        Devolve `None` quando o atendimento não está mais ativo para quem escreve. Um
        `client_message_id` repetido na conversa levanta `HandoffMessageConflict`.
        """
        existing = await self._session.scalar(
            select(Message.id).where(
                Message.conversation_id == conversation_id,
                Message.client_message_id == client_message_id,
            )
        )
        if existing is not None:
            raise HandoffMessageConflict(existing)
        # 1.
        conditions: list[ColumnElement[bool]] = [
            Handoff.id == handoff_id,
            Handoff.status != "closed",
        ]
        if attendant_id is not None:
            conditions += [Handoff.status == "assigned", Handoff.attendant_id == attendant_id]
        seq = await self._session.scalar(
            update(Handoff)
            .where(*conditions)
            .values(last_seq=Handoff.last_seq + 1, last_activity_at=now)
            .returning(Handoff.last_seq)
        )
        if seq is None:
            return None
        # 2.
        created_at = await self._allocate_created_at(conversation_id, now)
        row = Message(
            conversation_id=conversation_id,
            client_message_id=client_message_id,
            role=role,
            content=content,
            citations=[],
            input_tokens=0,
            output_tokens=0,
            handoff_id=handoff_id,
            seq=int(seq),
            author_user_id=author_user_id,
            created_at=created_at,
        )
        self._session.add(row)
        await self._session.flush()
        # 3.
        await self.notify(handoff_id, int(seq), NoticeKind.MESSAGE)
        return _message(row)

    async def redact_message(
        self,
        *,
        handoff_id: UUID,
        message_id: UUID,
        attendant_id: UUID,
        category: str,
        now: datetime,
    ) -> HandoffMessageRecord | None:
        """Troca o texto pelo marcador e apaga o original, sem cópia (seção 29.9.6).

        A mensagem ganha um `seq` novo, para o fluxo do visitante reenviá-la e a visão trocar
        o texto pelo id. Só no atendimento `assigned` à pessoa. Devolve `None` se a mensagem
        não é deste atendimento ou se o atendimento não é mais de quem pede.
        """
        found = await self._session.scalar(
            select(Message.id).where(Message.id == message_id, Message.handoff_id == handoff_id)
        )
        if found is None:
            return None
        seq = await self._session.scalar(
            update(Handoff)
            .where(
                Handoff.id == handoff_id,
                Handoff.status == "assigned",
                Handoff.attendant_id == attendant_id,
            )
            .values(last_seq=Handoff.last_seq + 1)
            .returning(Handoff.last_seq)
        )
        if seq is None:
            return None
        row = await self._session.scalar(
            update(Message)
            .where(Message.id == message_id)
            .values(content=REDACTED_MARKER, redaction=category, redacted_at=now, seq=int(seq))
            .returning(Message)
            .execution_options(populate_existing=True)
        )
        if row is None:
            return None
        await self.notify(handoff_id, int(seq), NoticeKind.MESSAGE)
        return _message(row)

    async def messages_after(self, handoff_id: UUID, after_seq: int) -> list[HandoffMessageRecord]:
        """As mensagens do atendimento com `seq` maior que `after_seq`, em ordem (29.6)."""
        rows = await self._session.scalars(
            select(Message)
            .where(Message.handoff_id == handoff_id, Message.seq > after_seq)
            .order_by(Message.seq.asc())
            .execution_options(populate_existing=True)
        )
        return [_message(row) for row in rows]

    async def message_count(self, handoff_id: UUID) -> int:
        """Quantas mensagens o atendimento tem, para a lista do admin."""
        value = await self._session.scalar(
            select(func.count()).select_from(Message).where(Message.handoff_id == handoff_id)
        )
        return int(value or 0)

    async def touch_visitor(self, handoff_id: UUID, now: datetime) -> None:
        """O sinal do fluxo do visitante, gravado a cada tique (seção 29.6)."""
        await self._session.execute(
            update(Handoff)
            .where(Handoff.id == handoff_id, Handoff.status != "closed")
            .values(visitor_seen_at=now)
        )

    async def presence(self, user_id: UUID) -> tuple[str, datetime] | None:
        """O status marcado e o último sinal da pessoa, ou `None` sem linha."""
        row = await self._session.get(AttendantPresence, user_id, populate_existing=True)
        if row is None:
            return None
        return row.status, row.last_seen_at

    async def set_presence(self, user_id: UUID, status: str, now: datetime) -> None:
        """Grava o status do `PresenceToggle` com um upsert, já com o sinal de agora."""
        statement = insert(AttendantPresence).values(
            user_id=user_id, status=status, last_seen_at=now
        )
        await self._session.execute(
            statement.on_conflict_do_update(
                index_elements=[AttendantPresence.user_id],
                set_={"status": status, "last_seen_at": now},
            )
        )

    async def touch_presence(self, user_id: UUID, now: datetime) -> None:
        """O sinal do console a cada tique. Sem linha, a pessoa entra como `away`."""
        statement = insert(AttendantPresence).values(
            user_id=user_id, status=PresenceStatus.AWAY.value, last_seen_at=now
        )
        await self._session.execute(
            statement.on_conflict_do_update(
                index_elements=[AttendantPresence.user_id],
                set_={"last_seen_at": now},
            )
        )

    async def delete_presence(self, user_id: UUID) -> None:
        """Apaga a presença da pessoa, na revogação do papel (seção 29.3)."""
        row = await self._session.get(AttendantPresence, user_id)
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()

    async def has_acknowledged(self, user_id: UUID, version: str) -> bool:
        """Se a pessoa aceitou esta versão do compromisso (seção 29.3)."""
        value = await self._session.scalar(
            select(func.count())
            .select_from(AttendantAcknowledgement)
            .where(
                AttendantAcknowledgement.user_id == user_id,
                AttendantAcknowledgement.version == version,
            )
        )
        return bool(value)

    async def acknowledge(self, user_id: UUID, version: str, now: datetime) -> None:
        """Grava o aceite. Aceitar de novo a mesma versão não muda nada."""
        await self._session.execute(
            insert(AttendantAcknowledgement)
            .values(user_id=user_id, version=version, accepted_at=now)
            .on_conflict_do_nothing()
        )

    async def closed_since(self, start: datetime, limit: int = 100) -> list[ClosedHandoff]:
        """Até `limit` atendimentos encerrados desde `start`, do mais recente ao mais antigo."""
        count = (
            select(func.count())
            .where(Message.handoff_id == Handoff.id)
            .correlate(Handoff)
            .scalar_subquery()
        )
        rows = await self._session.execute(
            select(Handoff, count)
            .where(Handoff.status == "closed", Handoff.closed_at >= start)
            .order_by(Handoff.closed_at.desc(), Handoff.id.desc())
            .limit(limit)
        )
        return [ClosedHandoff(record=_record(row), message_count=int(total)) for row, total in rows]

    async def release_all_for(self, attendant_id: UUID, now: datetime) -> list[UUID]:
        """Devolve à fila os atendimentos da pessoa, na revogação do papel (seção 29.3)."""
        return await self._sweep(
            (Handoff.status == "assigned", Handoff.attendant_id == attendant_id),
            {"status": HandoffStatus.QUEUED.value, "attendant_id": None, "queued_at": now},
        )

    async def sweep_queue_timeout(self, now: datetime) -> list[UUID]:
        """Fila há 15 minutos desde `queued_at` vira `queue_timeout` (seção 29.5)."""
        return await self._sweep(
            (Handoff.status == "queued", Handoff.queued_at < now - QUEUE_TIMEOUT),
            _closed(CloseReason.QUEUE_TIMEOUT, now),
        )

    async def sweep_visitor_left(self, now: datetime) -> list[UUID]:
        """Fila sem fluxo do visitante há 5 minutos vira `visitor_left`.

        Não vale para o canal WhatsApp: lá não há fluxo do visitante, e a fila vence só
        pela espera de 15 minutos (seção 30.5).
        """
        return await self._sweep(
            (
                Handoff.status == "queued",
                Handoff.channel == "web",
                Handoff.visitor_seen_at < now - VISITOR_ABSENT,
            ),
            _closed(CloseReason.VISITOR_LEFT, now),
        )

    async def sweep_inactivity(self, now: datetime) -> list[UUID]:
        """Atendimento `assigned` sem mensagem há 30 minutos vira `inactivity`."""
        return await self._sweep(
            (Handoff.status == "assigned", Handoff.last_activity_at < now - ASSIGNED_IDLE),
            _closed(CloseReason.INACTIVITY, now),
        )

    async def sweep_attendant_gone(self, now: datetime) -> list[UUID]:
        """Volta à fila o atendimento de quem ficou 2 minutos sem sinal no console."""
        recent = select(AttendantPresence.user_id).where(
            AttendantPresence.last_seen_at >= now - ATTENDANT_GONE
        )
        return await self._sweep(
            (Handoff.status == "assigned", Handoff.attendant_id.not_in(recent)),
            {"status": HandoffStatus.QUEUED.value, "attendant_id": None, "queued_at": now},
        )

    async def sweep_service_closed(self, now: datetime) -> list[UUID]:
        """Com o serviço desligado, a fila encerra; os assumidos terminam (seção 29.5)."""
        return await self._sweep(
            (Handoff.status == "queued",),
            _closed(CloseReason.SERVICE_CLOSED, now),
        )

    async def _transition(
        self, conditions: Sequence[ColumnElement[bool]], values: dict[str, object]
    ) -> HandoffRecord | None:
        """Um `UPDATE` condicional com `RETURNING`. Sem linha que casa, `None`."""
        row = await self._session.scalar(
            update(Handoff)
            .where(*conditions)
            .values(**values)
            .returning(Handoff)
            .execution_options(populate_existing=True)
        )
        return None if row is None else _record(row)

    async def _sweep(
        self, conditions: Sequence[ColumnElement[bool]], values: dict[str, object]
    ) -> list[UUID]:
        """Um passo da varredura: `UPDATE` condicional e um `NOTIFY` por atendimento."""
        rows = (
            await self._session.execute(
                update(Handoff)
                .where(*conditions)
                .values(**values)
                .returning(Handoff.id, Handoff.last_seq)
            )
        ).all()
        for handoff_id, seq in rows:
            await self.notify(handoff_id, int(seq), NoticeKind.STATUS)
        return [handoff_id for handoff_id, _seq in rows]

    async def _allocate_created_at(self, conversation_id: UUID, now: datetime) -> datetime:
        """Um instante depois da mensagem mais nova da conversa, como em `conversations.py`."""
        latest = await self._session.scalar(
            select(func.max(Message.created_at)).where(Message.conversation_id == conversation_id)
        )
        if not isinstance(latest, datetime) or latest < now:
            return now
        return latest + timedelta(microseconds=1)


def _subject_handoffs(user_id: UUID | None, guest_key_id: UUID | None) -> Select[Handoff]:
    """Os atendimentos das conversas do visitante: do membro ou da chave de convidado."""
    owner = (
        Conversation.user_id == user_id
        if user_id is not None
        else and_(Conversation.user_id.is_(None), Conversation.guest_key_id == guest_key_id)
    )
    return (
        select(Handoff).join(Conversation, Conversation.id == Handoff.conversation_id).where(owner)
    )


def _closed(reason: CloseReason, now: datetime) -> dict[str, object]:
    """Os valores de um encerramento pela varredura."""
    return {"status": HandoffStatus.CLOSED.value, "close_reason": reason.value, "closed_at": now}


def _record(row: Handoff) -> HandoffRecord:
    """Copia a entidade num registro imutável."""
    return HandoffRecord(
        id=row.id,
        conversation_id=row.conversation_id,
        status=row.status,
        trigger=row.trigger,
        trigger_message_id=row.trigger_message_id,
        attendant_id=row.attendant_id,
        close_reason=row.close_reason,
        requested_at=row.requested_at,
        queued_at=row.queued_at,
        assigned_at=row.assigned_at,
        closed_at=row.closed_at,
        last_activity_at=row.last_activity_at,
        visitor_seen_at=row.visitor_seen_at,
        last_seq=row.last_seq,
        content_purged_at=row.content_purged_at,
        channel=row.channel,
    )


def _message(row: Message) -> HandoffMessageRecord:
    """Copia a mensagem do atendimento num registro imutável.

    As restrições do banco garantem `handoff_id` e `seq` numa mensagem do atendimento.
    """
    if row.handoff_id is None or row.seq is None:
        raise ValueError("message outside a handoff")
    return HandoffMessageRecord(
        id=row.id,
        handoff_id=row.handoff_id,
        seq=row.seq,
        role=row.role,
        content=row.content,
        redaction=row.redaction,
        client_message_id=row.client_message_id,
        author_user_id=row.author_user_id,
        created_at=row.created_at,
    )
