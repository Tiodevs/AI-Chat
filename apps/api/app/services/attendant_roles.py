"""Concessão e revogação do papel `attendant`, só pela linha de comando. Seção 29.3 do SDD.

Camada de serviço. Só o script `app/scripts/attendants.py` usa: nenhuma rota da web concede
papel (decisão D-6). Usa `UserRepository`, `AuthSessionRepository`, `HandoffRepository` e
`AuditRepository`. Cada operação é uma transação, com o evento de auditoria nela.
"""

from dataclasses import dataclass
from uuid import UUID

from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.auth import normalize_email
from app.domain.errors import Conflict, NotFound, ValidationFailed
from app.ports.clock import Clock
from app.prompts.handoff import (
    SCRIPT_NOT_ADMIN,
    SCRIPT_NOT_ATTENDANT,
    SCRIPT_NOT_FOUND,
    SCRIPT_NOT_MEMBER,
    SCRIPT_REFUSE_ADMIN,
)
from app.repositories.audit import AuditRepository
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.handoffs import HandoffRepository
from app.repositories.users import UserRepository


@dataclass(frozen=True, slots=True)
class RoleChange:
    """O que o script imprime: a conta mudada, as sessões revogadas e os atendimentos devolvidos."""

    user_id: UUID
    sessions_revoked: int
    handoffs_released: int


class AttendantRoleService:
    """Promove um membro a `attendant` e volta um `attendant` a membro (seção 29.3)."""

    def __init__(self, *, database_url: str, clock: Clock) -> None:
        self._database_url = database_url
        self._clock = clock

    async def grant(self, email: str, *, by: str) -> RoleChange:
        """Promove a conta `member` do e-mail e revoga as sessões dela.

        Exige que `by` seja de um admin (a auditoria `attendant.grant` o registra como ator).
        Recusa mudar um admin e qualquer conta que não seja `member`.
        """
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            users = UserRepository(session)
            admin_id = await _admin_id(users, by)
            user = await users.get_by_email(normalize_email(email))
            if user is None:
                raise NotFound(SCRIPT_NOT_FOUND)
            if user.role == "admin":
                raise Conflict(SCRIPT_REFUSE_ADMIN)
            if user.role != "member":
                raise Conflict(SCRIPT_NOT_MEMBER)
            await users.set_role(user.id, "attendant", now)
            revoked = await AuthSessionRepository(session).revoke_for_user(user.id, now)
            await AuditRepository(session).record(
                actor_user_id=admin_id,
                action="attendant.grant",
                target_type="user",
                target_id=user.id,
                created_at=now,
            )
            change = RoleChange(user_id=user.id, sessions_revoked=revoked, handoffs_released=0)
        return change

    async def revoke(self, email: str, *, by: str) -> RoleChange:
        """Volta a conta `attendant` a `member`, na hora (seção 29.9.12, passo 1).

        Devolve à fila os atendimentos dela, apaga a presença, revoga as sessões e grava
        `attendant.revoke`. O `NOTIFY` da devolução avisa os fluxos da API, que fecham o
        console da pessoa no próximo tique.
        """
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            users = UserRepository(session)
            admin_id = await _admin_id(users, by)
            user = await users.get_by_email(normalize_email(email))
            if user is None:
                raise NotFound(SCRIPT_NOT_FOUND)
            if user.role == "admin":
                raise Conflict(SCRIPT_REFUSE_ADMIN)
            if user.role != "attendant":
                raise Conflict(SCRIPT_NOT_ATTENDANT)
            await users.set_role(user.id, "member", now)
            handoffs = HandoffRepository(session)
            released = await handoffs.release_all_for(user.id, now)
            await handoffs.delete_presence(user.id)
            revoked = await AuthSessionRepository(session).revoke_for_user(user.id, now)
            await AuditRepository(session).record(
                actor_user_id=admin_id,
                action="attendant.revoke",
                target_type="user",
                target_id=user.id,
                created_at=now,
            )
            change = RoleChange(
                user_id=user.id, sessions_revoked=revoked, handoffs_released=len(released)
            )
        return change


async def _admin_id(users: UserRepository, email: str) -> UUID:
    """O id do admin de `--by`. Outro papel, ou e-mail desconhecido, responde 422."""
    admin = await users.get_by_email(normalize_email(email))
    if admin is None or admin.role != "admin":
        raise ValidationFailed(SCRIPT_NOT_ADMIN)
    return admin.id
