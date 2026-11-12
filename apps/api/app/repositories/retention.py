"""Apagamentos da retenção, um por regra da seção 11.6. Cada um devolve a contagem.

Camada de repositório (seção 6.2 do SDD). Quem usa é o `RetentionService`, que o
`retention-job` (`python -m app.scripts.retention`) roda todo dia: uma regra por transação, e
cada uma grava a própria linha em `retention_runs` na mesma transação. O corte vem de
`app.domain.retention.cutoff`: vence o que tem marca de tempo estritamente anterior a ele. A
contagem é a das linhas que o DELETE principal devolve em `RETURNING`; o que some em cascata
não entra nela. Seções 8.1 e 18.3 do SDD.
"""

from datetime import datetime

from sqlalchemy import ColumnElement, and_, delete, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.handoff import RETENTION_MARKER, HandoffStatus, RedactionCategory
from app.models.audit_event import AuditEvent
from app.models.auth_session import AuthSession
from app.models.conversation import Conversation
from app.models.data_subject_request import DataSubjectRequest
from app.models.guest_key import GuestKey
from app.models.handoff import Handoff
from app.models.message import Message
from app.models.rate_limit_window import RateLimitWindow
from app.models.registration_session import RegistrationSession
from app.models.retention_run import RetentionRun
from app.models.user import User


class RetentionRepository:
    """Um método por regra de retenção, mais o registro da execução."""

    def __init__(self, session: AsyncSession) -> None:
        """Usa a sessão aberta pelo serviço, sem abrir transação própria."""
        self._session = session

    async def record_run(self, rule: str, deleted_count: int, ran_at: datetime) -> None:
        """Acrescenta a linha de `retention_runs` da regra.

        Não há `flush()`: o INSERT sai no commit da mesma transação que apagou, então a
        contagem e o apagamento ficam juntos ou não ficam.
        """
        self._session.add(RetentionRun(rule=rule, deleted_count=deleted_count, ran_at=ran_at))

    async def delete_inactive_accounts(self, cutoff: datetime) -> int:
        """Membros sem entrar desde o corte. Admins ficam de fora (seção 10.5).

        O corte é 24 meses (730 dias) antes de agora, comparado com `last_seen_at`.

        1. Apaga as sessões de autenticação desses membros, porque `auth_sessions.user_id`
           não tem cascata e travaria a exclusão.
        2. Apaga os membros. A cascata leva consentimentos, sessões de cadastro, conversas,
           mensagens e feedback, e os pedidos de titular ficam com `user_id` nulo.

        Devolve quantos membros saíram.
        """
        # 1. `stale` é uma subconsulta: o DELETE vira `WHERE user_id IN (SELECT id ...)`.
        stale = select(User.id).where(User.role == "member", User.last_seen_at < cutoff)
        await self._session.execute(delete(AuthSession).where(AuthSession.user_id.in_(stale)))
        # 2.
        result = await self._session.execute(
            delete(User).where(User.role == "member", User.last_seen_at < cutoff).returning(User.id)
        )
        return len(result.all())

    async def delete_member_conversations(self, cutoff: datetime) -> int:
        """Conversas de membro sem atividade há 12 meses (365 dias)."""
        return await self._delete_conversations(
            Conversation.user_id.is_not(None),
            cutoff,
        )

    async def delete_guest_conversations(self, cutoff: datetime) -> int:
        """Conversas de convidado sem atividade há 30 dias."""
        return await self._delete_conversations(
            Conversation.user_id.is_(None),
            cutoff,
        )

    async def delete_guest_keys(self, cutoff: datetime) -> int:
        """O cookie de convidado já expirou. Conversas que viraram de membro ficam.

        O corte é 30 dias depois da criação da chave, o mesmo prazo do cookie `atrium_guest`.

        1. Solta a chave das conversas que já têm membro, gravando `guest_key_id` nulo, para
           a cascata não levá-las.
        2. Apaga as chaves vencidas. A cascata de `conversations.guest_key_id` leva as
           conversas de convidado que ainda dependem delas, mesmo com mensagem recente: sem o
           cookie, ninguém mais as abre.

        Devolve quantas chaves saíram.
        """
        # 1.
        expired = select(GuestKey.id).where(GuestKey.created_at < cutoff)
        await self._session.execute(
            update(Conversation)
            .where(Conversation.guest_key_id.in_(expired), Conversation.user_id.is_not(None))
            .values(guest_key_id=None)
        )
        # 2.
        result = await self._session.execute(
            delete(GuestKey).where(GuestKey.created_at < cutoff).returning(GuestKey.id)
        )
        return len(result.all())

    async def delete_registration_sessions(self, cutoff: datetime) -> int:
        """Sessões de cadastro com `expires_at` antes do corte.

        O corte é o próprio agora, porque a sessão já expira 24 horas depois do início. Sai
        toda sessão vencida, inclusive as concluídas.
        """
        result = await self._session.execute(
            delete(RegistrationSession)
            .where(RegistrationSession.expires_at < cutoff)
            .returning(RegistrationSession.id)
        )
        return len(result.all())

    async def delete_auth_sessions(self, cutoff: datetime) -> int:
        """Sessões que expiraram ou foram revogadas há mais de 14 dias.

        `revoked_at` nulo nunca é menor que o corte, então uma sessão viva só sai pela
        expiração.
        """
        result = await self._session.execute(
            delete(AuthSession)
            .where(or_(AuthSession.expires_at < cutoff, AuthSession.revoked_at < cutoff))
            .returning(AuthSession.id)
        )
        return len(result.all())

    async def delete_rate_limit_windows(self, cutoff: datetime) -> int:
        """Janelas de limite de taxa que começaram há mais de 48 horas."""
        result = await self._session.execute(
            delete(RateLimitWindow)
            .where(RateLimitWindow.window_start < cutoff)
            .returning(RateLimitWindow.bucket_key)
        )
        return len(result.all())

    async def delete_audit_events(self, cutoff: datetime) -> int:
        """Eventos de auditoria com mais de 2 anos (730 dias)."""
        result = await self._session.execute(
            delete(AuditEvent).where(AuditEvent.created_at < cutoff).returning(AuditEvent.id)
        )
        return len(result.all())

    async def delete_privacy_requests(self, cutoff: datetime) -> int:
        """Só pedidos fechados. Um pedido aberto nunca vence.

        O corte é 2 anos depois do fechamento. Um pedido aberto tem `closed_at` nulo, e a
        comparação com nulo nunca é verdadeira no SQL.
        """
        result = await self._session.execute(
            delete(DataSubjectRequest)
            .where(DataSubjectRequest.closed_at < cutoff)
            .returning(DataSubjectRequest.id)
        )
        return len(result.all())

    async def _delete_conversations(self, owner: ColumnElement[bool], cutoff: datetime) -> int:
        """A última atividade é a mensagem mais nova, ou a criação sem mensagens.

        `owner` escolhe as conversas de membro ou as de convidado. `last_activity` é uma
        subconsulta correlacionada: para cada conversa, o `max(created_at)` das mensagens
        dela, pelo índice de `messages.conversation_id`. `exists()` diz se a conversa tem
        alguma mensagem. As mensagens e o feedback saem em cascata.
        """
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
        # Uma conversa com atendimento ativo fica: a varredura encerra o atendimento antes
        # (seção 29.9.9).
        active_handoff = exists().where(
            Handoff.conversation_id == Conversation.id,
            Handoff.status != HandoffStatus.CLOSED,
        )
        result = await self._session.execute(
            delete(Conversation).where(owner, stale, ~active_handoff).returning(Conversation.id)
        )
        return len(result.all())

    async def purge_handoff_content(self, cutoff: datetime) -> int:
        """O texto dos atendimentos encerrados antes do corte, 90 dias (seção 29.9.9).

        Troca o conteúdo de cada mensagem do atendimento pelo marcador de retenção, com
        `redaction = retention`, e grava `handoffs.content_purged_at`. O registro do
        atendimento e as mensagens ficam, sem texto. Um atendimento ativo nunca entra, porque
        só `closed` tem `closed_at`. Devolve quantas mensagens perderam o texto.
        """
        due = select(Handoff.id).where(
            Handoff.status == HandoffStatus.CLOSED,
            Handoff.closed_at < cutoff,
            Handoff.content_purged_at.is_(None),
        )
        result = await self._session.execute(
            update(Message)
            .where(
                Message.handoff_id.in_(due),
                or_(Message.redaction.is_(None), Message.redaction != "retention"),
            )
            .values(
                content=RETENTION_MARKER,
                redaction=RedactionCategory.RETENTION.value,
                redacted_at=func.now(),
            )
            .returning(Message.id)
        )
        purged = len(result.all())
        await self._session.execute(
            update(Handoff).where(Handoff.id.in_(due)).values(content_purged_at=func.now())
        )
        return purged
