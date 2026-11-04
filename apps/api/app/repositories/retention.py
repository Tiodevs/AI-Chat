"""Apagamentos da retenção, um por regra da seção 11.6. Cada um devolve a contagem."""

from datetime import datetime

from sqlalchemy import ColumnElement, and_, delete, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_event import AuditEvent
from app.models.auth_session import AuthSession
from app.models.conversation import Conversation
from app.models.data_subject_request import DataSubjectRequest
from app.models.guest_key import GuestKey
from app.models.message import Message
from app.models.rate_limit_window import RateLimitWindow
from app.models.registration_session import RegistrationSession
from app.models.user import User


class RetentionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def delete_inactive_accounts(self, cutoff: datetime) -> int:
        """Membros sem entrar desde o corte. Admins ficam de fora (seção 10.5)."""
        stale = select(User.id).where(User.role == "member", User.last_seen_at < cutoff)
        await self._session.execute(delete(AuthSession).where(AuthSession.user_id.in_(stale)))
        result = await self._session.execute(
            delete(User).where(User.role == "member", User.last_seen_at < cutoff).returning(User.id)
        )
        return len(result.all())

    async def delete_member_conversations(self, cutoff: datetime) -> int:
        return await self._delete_conversations(
            Conversation.user_id.is_not(None),
            cutoff,
        )

    async def delete_guest_conversations(self, cutoff: datetime) -> int:
        return await self._delete_conversations(
            Conversation.user_id.is_(None),
            cutoff,
        )

    async def delete_guest_keys(self, cutoff: datetime) -> int:
        """O cookie de convidado já expirou. Conversas que viraram de membro ficam."""
        expired = select(GuestKey.id).where(GuestKey.created_at < cutoff)
        await self._session.execute(
            update(Conversation)
            .where(Conversation.guest_key_id.in_(expired), Conversation.user_id.is_not(None))
            .values(guest_key_id=None)
        )
        result = await self._session.execute(
            delete(GuestKey).where(GuestKey.created_at < cutoff).returning(GuestKey.id)
        )
        return len(result.all())

    async def delete_registration_sessions(self, cutoff: datetime) -> int:
        result = await self._session.execute(
            delete(RegistrationSession)
            .where(RegistrationSession.expires_at < cutoff)
            .returning(RegistrationSession.id)
        )
        return len(result.all())

    async def delete_auth_sessions(self, cutoff: datetime) -> int:
        result = await self._session.execute(
            delete(AuthSession)
            .where(or_(AuthSession.expires_at < cutoff, AuthSession.revoked_at < cutoff))
            .returning(AuthSession.id)
        )
        return len(result.all())

    async def delete_rate_limit_windows(self, cutoff: datetime) -> int:
        result = await self._session.execute(
            delete(RateLimitWindow)
            .where(RateLimitWindow.window_start < cutoff)
            .returning(RateLimitWindow.bucket_key)
        )
        return len(result.all())

    async def delete_audit_events(self, cutoff: datetime) -> int:
        result = await self._session.execute(
            delete(AuditEvent).where(AuditEvent.created_at < cutoff).returning(AuditEvent.id)
        )
        return len(result.all())

    async def delete_privacy_requests(self, cutoff: datetime) -> int:
        """Só pedidos fechados. Um pedido aberto nunca vence."""
        result = await self._session.execute(
            delete(DataSubjectRequest)
            .where(DataSubjectRequest.closed_at < cutoff)
            .returning(DataSubjectRequest.id)
        )
        return len(result.all())

    async def _delete_conversations(self, owner: ColumnElement[bool], cutoff: datetime) -> int:
        """A última atividade é a mensagem mais nova, ou a criação sem mensagens."""
        last_activity = (
            select(func.max(Message.created_at))
            .where(Message.conversation_id == Conversation.id)
            .scalar_subquery()
        )
        has_messages = exists().where(Message.conversation_id == Conversation.id)
        stale = or_(
            and_(has_messages, last_activity < cutoff),
            and_(~has_messages, Conversation.created_at < cutoff),
        )
        result = await self._session.execute(
            delete(Conversation).where(owner, stale).returning(Conversation.id)
        )
        return len(result.all())
