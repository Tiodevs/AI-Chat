"""Quem pede pelo lado do visitante: o membro da sessão ou a chave de convidado. Seção 7.1.

Camada de serviço. `services/handoff.py` resolve o visitante aqui em cada pedido e em cada
tique do fluxo do atendimento (seção 29.6). A regra é a mesma do `ConversationService`: uma
sessão que não resolve responde 401 mesmo com a chave de convidado válida, e a chave só abre a
conversa sem membro (`domain/questions.py:owns_conversation`, Etapa 15.1).
"""

from dataclasses import dataclass
from uuid import UUID

from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.auth import hash_session_secret
from app.domain.errors import Unauthenticated
from app.domain.questions import owns_conversation
from app.ports.clock import Clock
from app.prompts.auth import UNAUTHENTICATED
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.conversations import ConversationRecord, ConversationRepository


@dataclass(frozen=True, slots=True)
class Visitor:
    """O membro, a chave de convidado, ou os dois, de quem fez o pedido."""

    user_id: UUID | None
    guest_key_id: UUID | None

    @property
    def subject_id(self) -> UUID:
        """O sujeito dos limites e da regra de um atendimento ativo: o membro ou a chave."""
        subject = self.user_id or self.guest_key_id
        if subject is None:
            raise ValueError("visitor without subject")
        return subject

    def owns(self, conversation: ConversationRecord) -> bool:
        """A regra de dono do domínio, aplicada à conversa."""
        return owns_conversation(
            actor_user_id=self.user_id,
            actor_guest_key_id=self.guest_key_id,
            owner_user_id=conversation.user_id,
            owner_guest_key_id=conversation.guest_key_id,
        )


async def resolve_visitor(
    database_url: str,
    clock: Clock,
    *,
    session_secret: str | None,
    guest_secret: str | None,
) -> Visitor:
    """Lê a sessão e a chave de convidado numa transação curta. Sem nenhuma, 401.

    A sessão é procurada pelo SHA-256 do segredo, sem `revoked_at` e antes de `expires_at`; a
    chave de convidado, pelo SHA-256 do cookie.
    """
    user_id: UUID | None = None
    guest_id: UUID | None = None
    async with open_session(database_url) as session, UnitOfWork(session):
        if session_secret:
            found = await AuthSessionRepository(session).get_active(
                hash_session_secret(session_secret), clock.now()
            )
            if found is None:
                raise Unauthenticated(UNAUTHENTICATED)
            user_id = found.user_id
        if guest_secret:
            guest = await ConversationRepository(session).get_guest_key_by_hash(
                hash_session_secret(guest_secret)
            )
            guest_id = None if guest is None else guest.id
    if user_id is None and guest_id is None:
        raise Unauthenticated(UNAUTHENTICATED)
    return Visitor(user_id=user_id, guest_key_id=guest_id)
