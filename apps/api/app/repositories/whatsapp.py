"""Contatos, caixa de entrada, caixa de saída e repasse do WhatsApp. Seção 30.7 e ADR-017.

Camada de repositório (seção 6.2). Quem usa: `services/whatsapp_webhook.py` (grava a caixa de
entrada), `services/whatsapp.py` (o processador, o enviador e o repasse), a retenção e as
métricas lidas do banco. Nenhuma consulta devolve telefone para fora do envio: o telefone só
sai em `OutboundJob`, que vai direto para a porta `MessagingChannel`.

Pegar trabalho é um `UPDATE ... WHERE id = (SELECT ... FOR UPDATE SKIP LOCKED)`: duas réplicas
não pegam o mesmo evento nem a mesma mensagem, e nenhuma transação fica aberta durante uma
chamada à Meta ou ao modelo (seção 6.4).
"""

import hashlib
import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, delete, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.handoff import HandoffStatus
from app.domain.whatsapp import (
    MAX_PROCESS_ATTEMPTS,
    STALE_EVENT,
    STALE_PROCESSING,
    Channel,
    InboundEvent,
    InboundStatus,
    OutboundStatus,
    status_advances,
)
from app.models.conversation import Conversation
from app.models.guest_key import GuestKey
from app.models.handoff import Handoff
from app.models.message import Message
from app.models.whatsapp import (
    WhatsAppContact,
    WhatsAppHandoffRelay,
    WhatsAppInboundEvent,
    WhatsAppOutboundMessage,
)

# Quanto tempo uma mensagem pega pelo enviador fica reservada antes de outra tentativa.
_SEND_LEASE = timedelta(minutes=2)
_FINAL = (OutboundStatus.DELIVERED.value, OutboundStatus.READ.value, OutboundStatus.FAILED.value)


@dataclass(frozen=True, slots=True)
class ClaimedEvent:
    """Um evento pego pelo processador, com o que ele precisa e nada mais."""

    id: UUID
    kind: str
    identity: str | None
    phone: str | None
    previous_identity: str | None
    message_type: str | None
    body: str | None
    button_id: str | None
    wamid: str | None
    delivery_status: str | None
    error_code: int | None
    wa_timestamp: datetime
    attempts: int


@dataclass(frozen=True, slots=True)
class ContactRecord:
    """Um contato, sem o telefone: quem lê o contato não precisa dele."""

    id: UUID
    identity: str
    guest_key_id: UUID
    notice_version: str | None
    last_inbound_at: datetime


@dataclass(frozen=True, slots=True)
class OutboundJob:
    """Uma mensagem pega pelo enviador, com o destino do contato."""

    id: UUID
    kind: str
    payload: dict[str, Any]
    attempts: int
    used_phone: bool
    identity: str
    phone: str | None
    last_inbound_at: datetime


@dataclass(frozen=True, slots=True)
class RelayItem:
    """Um atendimento do WhatsApp com algo a repassar ao contato."""

    handoff_id: UUID
    conversation_id: UUID
    contact_id: UUID
    status: str
    close_reason: str | None
    assigned_at: datetime | None
    last_seq: int
    delivered_seq: int
    announced_status: str | None
    announced_assigned_at: datetime | None


@dataclass(frozen=True, slots=True)
class StaffLine:
    """Uma mensagem da equipe ainda não repassada."""

    message_id: UUID
    seq: int
    content: str


@dataclass(frozen=True, slots=True)
class Delivery:
    """O status de entrega de uma mensagem da equipe, para o console."""

    status: str
    error_code: int | None


class WhatsAppRepository:
    """Consultas e gravações do canal, na transação do serviço."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # Caixa de entrada.

    async def insert_events(self, events: Sequence[InboundEvent], now: datetime) -> int:
        """Grava os eventos do webhook. Uma chave repetida é ignorada (NFR-22).

        Um evento com mais de 7 dias entra como `ignored`: é uma repetição antiga da Meta.
        Devolve quantos entraram de fato.
        """
        inserted = 0
        for event in events:
            status = (
                InboundStatus.IGNORED
                if now - event.wa_timestamp > STALE_EVENT
                else InboundStatus.PENDING
            )
            result = await self._session.execute(
                insert(WhatsAppInboundEvent)
                .values(
                    event_key=event.event_key,
                    kind=event.kind.value,
                    identity=event.identity,
                    phone=event.phone,
                    previous_identity=event.previous_identity,
                    message_type=None if event.message_type is None else event.message_type.value,
                    body=event.body,
                    button_id=event.button_id,
                    wamid=event.wamid,
                    delivery_status=None if event.status is None else event.status.value,
                    error_code=event.error_code,
                    wa_timestamp=event.wa_timestamp,
                    received_at=now,
                    status=status.value,
                )
                .on_conflict_do_nothing(index_elements=["event_key"])
                .returning(WhatsAppInboundEvent.id)
            )
            if result.first() is not None:
                inserted += 1
        return inserted

    async def claim_event(self, now: datetime) -> ClaimedEvent | None:
        """Pega o próximo evento pendente, em ordem por pessoa (seção 30.4, passo 2).

        Um evento só é pego quando a mesma pessoa não tem evento mais antigo pendente nem
        outro em processamento. Um processamento parado há 5 minutos volta a valer.
        """
        stale = now - STALE_PROCESSING
        other = WhatsAppInboundEvent.__table__.alias("other")
        same_identity = other.c.identity == WhatsAppInboundEvent.identity
        blocked = exists().where(
            same_identity,
            other.c.id != WhatsAppInboundEvent.id,
            or_(
                and_(other.c.status == "processing", other.c.claimed_at >= stale),
                and_(
                    other.c.status == "pending",
                    other.c.wa_timestamp < WhatsAppInboundEvent.wa_timestamp,
                ),
            ),
        )
        candidate = (
            select(WhatsAppInboundEvent.id)
            .where(
                or_(
                    WhatsAppInboundEvent.status == "pending",
                    and_(
                        WhatsAppInboundEvent.status == "processing",
                        WhatsAppInboundEvent.claimed_at < stale,
                    ),
                ),
                or_(WhatsAppInboundEvent.identity.is_(None), ~blocked),
            )
            .order_by(WhatsAppInboundEvent.wa_timestamp, WhatsAppInboundEvent.received_at)
            .limit(1)
            .with_for_update(skip_locked=True)
            .scalar_subquery()
        )
        row = await self._session.scalar(
            update(WhatsAppInboundEvent)
            .where(WhatsAppInboundEvent.id == candidate)
            .values(
                status="processing",
                claimed_at=now,
                attempts=WhatsAppInboundEvent.attempts + 1,
            )
            .returning(WhatsAppInboundEvent)
        )
        if row is None:
            return None
        return ClaimedEvent(
            id=row.id,
            kind=row.kind,
            identity=row.identity,
            phone=row.phone,
            previous_identity=row.previous_identity,
            message_type=row.message_type,
            body=row.body,
            button_id=row.button_id,
            wamid=row.wamid,
            delivery_status=row.delivery_status,
            error_code=row.error_code,
            wa_timestamp=row.wa_timestamp,
            attempts=row.attempts,
        )

    async def finish_event(self, event_id: UUID, status: InboundStatus, now: datetime) -> None:
        """Fecha o evento e apaga texto, identidade e telefone (seção 30.7)."""
        await self._session.execute(
            update(WhatsAppInboundEvent)
            .where(WhatsAppInboundEvent.id == event_id)
            .values(
                status=status.value,
                processed_at=now,
                body=None,
                identity=None,
                phone=None,
                previous_identity=None,
            )
        )

    async def retry_event(self, event_id: UUID, attempts: int, now: datetime) -> bool:
        """Devolve o evento à fila ou, depois de 3 tentativas, o fecha como `failed`."""
        if attempts >= MAX_PROCESS_ATTEMPTS:
            await self.finish_event(event_id, InboundStatus.FAILED, now)
            return False
        await self._session.execute(
            update(WhatsAppInboundEvent)
            .where(WhatsAppInboundEvent.id == event_id)
            .values(status="pending", claimed_at=None)
        )
        return True

    # Contatos e conversas.

    async def lock_identity(self, identity: str) -> None:
        """Trava a criação do contato da mesma pessoa até o fim da transação."""
        await self._session.execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended(f"whatsapp:{identity}", 0)))
        )

    async def get_contact(self, identity: str) -> ContactRecord | None:
        row = await self._session.scalar(
            select(WhatsAppContact).where(WhatsAppContact.identity == identity)
        )
        return None if row is None else _contact(row)

    async def get_contact_by_id(self, contact_id: UUID) -> ContactRecord | None:
        row = await self._session.get(WhatsAppContact, contact_id)
        return None if row is None else _contact(row)

    async def contact_for_guest_key(self, guest_key_id: UUID) -> ContactRecord | None:
        row = await self._session.scalar(
            select(WhatsAppContact).where(WhatsAppContact.guest_key_id == guest_key_id)
        )
        return None if row is None else _contact(row)

    async def upsert_contact(
        self, *, identity: str, phone: str | None, now: datetime
    ) -> tuple[ContactRecord, bool]:
        """O contato da pessoa, criado com a chave de convidado interna na primeira vez.

        Atualiza `last_inbound_at` e, quando vem, o telefone. Devolve o contato e se ele é
        novo. A chave nasce com um segredo aleatório que ninguém recebe: ela nunca vira
        cookie e só serve de dona das conversas.
        """
        await self.lock_identity(identity)
        row = await self._session.scalar(
            select(WhatsAppContact).where(WhatsAppContact.identity == identity)
        )
        if row is not None:
            row.last_inbound_at = max(row.last_inbound_at, now)
            if phone:
                row.phone = phone
            await self._session.flush()
            return _contact(row), False
        guest = GuestKey(
            token_hash=hashlib.sha256(secrets.token_bytes(32)).hexdigest(), created_at=now
        )
        self._session.add(guest)
        await self._session.flush()
        row = WhatsAppContact(
            identity=identity,
            phone=phone,
            guest_key_id=guest.id,
            first_seen_at=now,
            last_inbound_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return _contact(row), True

    async def change_identity(self, *, previous: str, current: str, phone: str | None) -> bool:
        """Troca o BSUID do contato pelo novo (seção 30.4, passo 3). Sem contato, nada muda."""
        row = await self._session.scalar(
            select(WhatsAppContact).where(WhatsAppContact.identity == previous)
        )
        if row is None:
            return False
        taken = await self._session.scalar(
            select(WhatsAppContact.id).where(WhatsAppContact.identity == current)
        )
        if taken is not None:
            return False
        row.identity = current
        if phone:
            row.phone = phone
        await self._session.flush()
        return True

    async def set_notice_version(self, contact_id: UUID, version: str) -> None:
        await self._session.execute(
            update(WhatsAppContact)
            .where(WhatsAppContact.id == contact_id)
            .values(notice_version=version)
        )

    async def active_conversation(self, guest_key_id: UUID) -> tuple[UUID, datetime] | None:
        """A conversa mais nova do contato e a hora da última mensagem da pessoa nela."""
        conversation_id = await self._session.scalar(
            select(Conversation.id)
            .where(Conversation.guest_key_id == guest_key_id)
            .order_by(Conversation.created_at.desc(), Conversation.id.desc())
            .limit(1)
        )
        if conversation_id is None:
            return None
        last_user = await self._session.scalar(
            select(func.max(Message.created_at)).where(
                Message.conversation_id == conversation_id, Message.role == "user"
            )
        )
        created = await self._session.scalar(
            select(Conversation.created_at).where(Conversation.id == conversation_id)
        )
        moment = last_user if isinstance(last_user, datetime) else created
        if not isinstance(moment, datetime):
            return None
        return conversation_id, moment

    async def conversation_ids(self, guest_key_id: UUID) -> list[UUID]:
        """As conversas do contato, pela chave interna."""
        rows = await self._session.scalars(
            select(Conversation.id).where(Conversation.guest_key_id == guest_key_id)
        )
        return list(rows)

    async def delete_contact(self, contact_id: UUID) -> UUID | None:
        """Apaga a chave de convidado do contato. A cascata leva contato, conversas,
        atendimentos, mensagens e as linhas de saída (seção 30.9.6). Devolve a chave apagada.
        """
        guest_key_id = await self._session.scalar(
            select(WhatsAppContact.guest_key_id).where(WhatsAppContact.id == contact_id)
        )
        if guest_key_id is None:
            return None
        await self._session.execute(delete(GuestKey).where(GuestKey.id == guest_key_id))
        return guest_key_id

    # Caixa de saída.

    async def enqueue(
        self,
        *,
        contact_id: UUID,
        kind: str,
        payload: dict[str, Any],
        now: datetime,
        conversation_id: UUID | None = None,
        message_id: UUID | None = None,
        handoff_id: UUID | None = None,
        order: int = 0,
    ) -> UUID:
        """Grava uma mensagem de saída `pending`, pronta para o enviador.

        `order` soma microssegundos ao `created_at`: as saídas de uma mesma transação saem
        na ordem em que foram gravadas.
        """
        row = WhatsAppOutboundMessage(
            contact_id=contact_id,
            conversation_id=conversation_id,
            message_id=message_id,
            handoff_id=handoff_id,
            kind=kind,
            payload=payload,
            status=OutboundStatus.PENDING.value,
            next_attempt_at=now,
            created_at=now + timedelta(microseconds=order),
            updated_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return row.id

    async def claim_outbound(self, now: datetime) -> OutboundJob | None:
        """Pega a próxima mensagem vencida e a reserva por 2 minutos."""
        candidate = (
            select(WhatsAppOutboundMessage.id)
            .where(
                WhatsAppOutboundMessage.status == "pending",
                WhatsAppOutboundMessage.next_attempt_at <= now,
            )
            .order_by(WhatsAppOutboundMessage.created_at, WhatsAppOutboundMessage.id)
            .limit(1)
            .with_for_update(skip_locked=True)
            .scalar_subquery()
        )
        row = await self._session.scalar(
            update(WhatsAppOutboundMessage)
            .where(WhatsAppOutboundMessage.id == candidate)
            .values(next_attempt_at=now + _SEND_LEASE, updated_at=now)
            .returning(WhatsAppOutboundMessage)
        )
        if row is None:
            return None
        contact = await self._session.get(WhatsAppContact, row.contact_id)
        if contact is None:
            return None
        return OutboundJob(
            id=row.id,
            kind=row.kind,
            payload=dict(row.payload or {}),
            attempts=row.attempts,
            used_phone=row.used_phone,
            identity=contact.identity,
            phone=contact.phone,
            last_inbound_at=contact.last_inbound_at,
        )

    async def mark_sent(
        self, outbound_id: UUID, *, wamid: str, used_phone: bool, now: datetime
    ) -> None:
        await self._session.execute(
            update(WhatsAppOutboundMessage)
            .where(WhatsAppOutboundMessage.id == outbound_id)
            .values(
                status=OutboundStatus.SENT.value,
                wamid=wamid,
                used_phone=used_phone,
                attempts=WhatsAppOutboundMessage.attempts + 1,
                error_code=None,
                updated_at=now,
            )
        )

    async def mark_retry(
        self,
        outbound_id: UUID,
        *,
        next_attempt_at: datetime,
        error_code: int | None,
        used_phone: bool,
        now: datetime,
    ) -> None:
        await self._session.execute(
            update(WhatsAppOutboundMessage)
            .where(WhatsAppOutboundMessage.id == outbound_id)
            .values(
                attempts=WhatsAppOutboundMessage.attempts + 1,
                next_attempt_at=next_attempt_at,
                error_code=error_code,
                used_phone=used_phone,
                updated_at=now,
            )
        )

    async def mark_failed(
        self, outbound_id: UUID, *, error_code: int | None, now: datetime
    ) -> None:
        """Status final de falha, sem o texto."""
        await self._session.execute(
            update(WhatsAppOutboundMessage)
            .where(WhatsAppOutboundMessage.id == outbound_id)
            .values(
                status=OutboundStatus.FAILED.value,
                attempts=WhatsAppOutboundMessage.attempts + 1,
                error_code=error_code,
                payload=None,
                updated_at=now,
            )
        )

    async def apply_status(
        self, *, wamid: str, status: OutboundStatus, error_code: int | None, now: datetime
    ) -> bool:
        """Aplica o status do webhook sem voltar atrás. Apaga o texto no status final."""
        row = await self._session.scalar(
            select(WhatsAppOutboundMessage)
            .where(WhatsAppOutboundMessage.wamid == wamid)
            .with_for_update()
        )
        if row is None or not status_advances(row.status, status):
            return False
        row.status = status.value
        row.updated_at = now
        if error_code is not None:
            row.error_code = error_code
        if status.value in _FINAL:
            row.payload = None
        await self._session.flush()
        return True

    async def deliveries(self, message_ids: Sequence[UUID]) -> dict[UUID, Delivery]:
        """O status de entrega das mensagens da equipe, para o console (seção 30.5)."""
        if not message_ids:
            return {}
        rows = await self._session.execute(
            select(
                WhatsAppOutboundMessage.message_id,
                WhatsAppOutboundMessage.status,
                WhatsAppOutboundMessage.error_code,
            ).where(WhatsAppOutboundMessage.message_id.in_(list(message_ids)))
        )
        return {
            message_id: Delivery(status=status, error_code=error_code)
            for message_id, status, error_code in rows.all()
            if message_id is not None
        }

    # Repasse do atendimento.

    async def relay_candidates(self, limit: int = 20) -> list[UUID]:
        """Atendimentos do WhatsApp com mensagem da equipe ou status ainda não repassados."""
        relay = WhatsAppHandoffRelay
        rows = await self._session.scalars(
            select(Handoff.id)
            .outerjoin(relay, relay.handoff_id == Handoff.id)
            .where(
                Handoff.channel == Channel.WHATSAPP.value,
                or_(
                    relay.handoff_id.is_(None),
                    Handoff.last_seq > relay.delivered_seq,
                    relay.announced_status.is_distinct_from(Handoff.status),
                    relay.announced_assigned_at.is_distinct_from(Handoff.assigned_at),
                ),
            )
            .order_by(Handoff.requested_at)
            .limit(limit)
        )
        return list(rows)

    async def lock_relay(self, handoff_id: UUID) -> RelayItem | None:
        """Cria, se falta, e trava o cursor do atendimento, com o estado atual dele."""
        await self._session.execute(
            insert(WhatsAppHandoffRelay)
            .values(handoff_id=handoff_id)
            .on_conflict_do_nothing(index_elements=["handoff_id"])
        )
        relay = await self._session.scalar(
            select(WhatsAppHandoffRelay)
            .where(WhatsAppHandoffRelay.handoff_id == handoff_id)
            .with_for_update(skip_locked=True)
        )
        if relay is None:
            return None
        handoff = await self._session.get(Handoff, handoff_id)
        if handoff is None:
            return None
        contact_id = await self._session.scalar(
            select(WhatsAppContact.id)
            .join(Conversation, Conversation.guest_key_id == WhatsAppContact.guest_key_id)
            .where(Conversation.id == handoff.conversation_id)
        )
        if contact_id is None:
            return None
        return RelayItem(
            handoff_id=handoff_id,
            conversation_id=handoff.conversation_id,
            contact_id=contact_id,
            status=handoff.status,
            close_reason=handoff.close_reason,
            assigned_at=handoff.assigned_at,
            last_seq=handoff.last_seq,
            delivered_seq=relay.delivered_seq,
            announced_status=relay.announced_status,
            announced_assigned_at=relay.announced_assigned_at,
        )

    async def staff_lines_after(self, handoff_id: UUID, after_seq: int) -> list[StaffLine]:
        """As mensagens da equipe com `seq` maior, sem as removidas."""
        rows = await self._session.execute(
            select(Message.id, Message.seq, Message.content)
            .where(
                Message.handoff_id == handoff_id,
                Message.role == "attendant",
                Message.seq > after_seq,
                Message.redaction.is_(None),
            )
            .order_by(Message.seq)
        )
        return [
            StaffLine(message_id=message_id, seq=int(seq or 0), content=content)
            for message_id, seq, content in rows.all()
        ]

    async def advance_relay(
        self,
        handoff_id: UUID,
        *,
        delivered_seq: int,
        status: str,
        assigned_at: datetime | None,
    ) -> None:
        await self._session.execute(
            update(WhatsAppHandoffRelay)
            .where(WhatsAppHandoffRelay.handoff_id == handoff_id)
            .values(
                delivered_seq=delivered_seq,
                announced_status=status,
                announced_assigned_at=assigned_at,
            )
        )

    # Retenção e métricas.

    async def delete_stale_contacts(self, cutoff: datetime) -> int:
        """Contatos sem mensagem há 30 dias e sem atendimento ativo (seção 30.9.7)."""
        active = exists().where(
            Handoff.status != HandoffStatus.CLOSED.value,
            Handoff.conversation_id == Conversation.id,
            Conversation.guest_key_id == WhatsAppContact.guest_key_id,
        )
        stale = select(WhatsAppContact.guest_key_id).where(
            WhatsAppContact.last_inbound_at < cutoff, ~active
        )
        result = await self._session.execute(
            delete(GuestKey).where(GuestKey.id.in_(stale)).returning(GuestKey.id)
        )
        return len(result.all())

    async def delete_old_events(self, cutoff: datetime) -> int:
        """Linhas de entrada recebidas e de saída paradas há mais de 7 dias."""
        inbound = await self._session.execute(
            delete(WhatsAppInboundEvent)
            .where(
                WhatsAppInboundEvent.received_at < cutoff,
                WhatsAppInboundEvent.status.in_(["done", "failed", "ignored"]),
            )
            .returning(WhatsAppInboundEvent.id)
        )
        outbound = await self._session.execute(
            delete(WhatsAppOutboundMessage)
            .where(
                WhatsAppOutboundMessage.updated_at < cutoff,
                WhatsAppOutboundMessage.status != "pending",
            )
            .returning(WhatsAppOutboundMessage.id)
        )
        return len(inbound.all()) + len(outbound.all())

    async def pending_counts(self, now: datetime) -> dict[str, tuple[int, float]]:
        """Quantos pendentes há em cada direção e a idade do mais antigo, em segundos."""
        inbound = (
            await self._session.execute(
                select(func.count(), func.min(WhatsAppInboundEvent.received_at)).where(
                    WhatsAppInboundEvent.status.in_(["pending", "processing"])
                )
            )
        ).one()
        outbound = (
            await self._session.execute(
                select(func.count(), func.min(WhatsAppOutboundMessage.created_at)).where(
                    WhatsAppOutboundMessage.status == "pending"
                )
            )
        ).one()
        return {
            "inbound": (int(inbound[0]), _age(inbound[1], now)),
            "outbound": (int(outbound[0]), _age(outbound[1], now)),
        }

    async def service_messages_since(self, start: datetime) -> int:
        """Mensagens enviadas desde o início do mês, para comparar com a cota grátis."""
        count = await self._session.scalar(
            select(func.count()).where(
                WhatsAppOutboundMessage.created_at >= start,
                WhatsAppOutboundMessage.status.in_(["sent", "delivered", "read"]),
            )
        )
        return int(count or 0)


def _contact(row: WhatsAppContact) -> ContactRecord:
    return ContactRecord(
        id=row.id,
        identity=row.identity,
        guest_key_id=row.guest_key_id,
        notice_version=row.notice_version,
        last_inbound_at=row.last_inbound_at,
    )


def _age(moment: object, now: datetime) -> float:
    if not isinstance(moment, datetime):
        return 0.0
    return max(0.0, (now - moment).total_seconds())
