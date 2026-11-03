"""Conta do membro: perfil, exportação, consentimentos e exclusão. Seções 11.5 e 11.6."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.account import (
    ACCOUNT_DELETE_ACTION,
    CONSENT_CHANGE_ACTION,
    PERSONALIZED_FIELDS,
    delete_is_allowed,
    plan_profile_update,
    purpose_can_change,
)
from app.domain.errors import Forbidden, NotFound, ValidationFailed
from app.domain.legal import LEGAL_DOCUMENT_VERSION, needs_legal_acceptance
from app.domain.profile import Profile
from app.domain.registration import ConsentGrant, ConsentSource, Purpose
from app.models.consent_record import ConsentRecord
from app.models.user import User
from app.ports.clock import Clock
from app.prompts.account import (
    ADMIN_CANNOT_DELETE,
    PERSONALIZATION_REQUIRED,
    PROFILE_NOT_CHANGED,
    PURPOSE_NOT_CHANGEABLE,
    USER_NOT_FOUND,
)
from app.prompts.registration import message_for
from app.repositories.audit import AuditRepository
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.consents import ConsentRepository
from app.repositories.conversations import ConversationRepository
from app.repositories.users import UserRepository

_MANAGED_PURPOSES = (
    Purpose.TERMS.value,
    Purpose.AGE.value,
    Purpose.PERSONALIZATION.value,
    Purpose.QUALITY.value,
)


@dataclass(frozen=True, slots=True)
class ConsentView:
    purpose: str
    document_version: str
    granted_at: datetime
    revoked_at: datetime | None
    source: str


@dataclass(frozen=True, slots=True)
class ConsentState:
    purpose: str
    granted: bool
    document_version: str | None
    granted_at: datetime | None


@dataclass(frozen=True, slots=True)
class ConsentOverview:
    current: tuple[ConsentState, ...]
    history: tuple[ConsentView, ...]


@dataclass(frozen=True, slots=True)
class ExportedCitation:
    index: int
    document_title: str
    heading: str | None


@dataclass(frozen=True, slots=True)
class ExportedMessage:
    role: str
    content: str
    citations: tuple[ExportedCitation, ...]
    outcome: str | None
    feedback: int | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ExportedConversation:
    id: UUID
    created_at: datetime
    messages: tuple[ExportedMessage, ...]


@dataclass(frozen=True, slots=True)
class DataExport:
    exported_at: datetime
    email: str
    full_name: str
    phone: str | None
    visitor_type: str | None
    visit_reason: str | None
    role: str
    created_at: datetime
    consents: tuple[ConsentView, ...]
    conversations: tuple[ExportedConversation, ...]


class AccountService:
    def __init__(self, *, database_url: str, clock: Clock) -> None:
        self._database_url = database_url
        self._clock = clock

    async def update_profile(self, user_id: UUID, changes: dict[str, str | None]) -> Profile:
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            users = UserRepository(session)
            user = await _require_user(users, user_id)
            personalization = await ConsentRepository(session).has_active(
                user_id, Purpose.PERSONALIZATION.value
            )
            plan = plan_profile_update(changes, personalization_active=personalization)
            if plan.issues:
                raise ValidationFailed(
                    PROFILE_NOT_CHANGED,
                    field_errors={
                        issue.field: _issue_message(issue.field, issue.code)
                        for issue in plan.issues
                    },
                )
            await users.update_profile(user_id, plan.values, now)
            await session.refresh(user)
            profile = await _profile(session, user)
        return profile

    async def consents(self, user_id: UUID) -> ConsentOverview:
        async with open_session(self._database_url) as session, UnitOfWork(session):
            await _require_user(UserRepository(session), user_id)
            records = await ConsentRepository(session).list_for_user(user_id)
        return _overview(records)

    async def set_consent(self, user_id: UUID, purpose: str, *, granted: bool) -> ConsentOverview:
        if not purpose_can_change(purpose, granted=granted):
            raise ValidationFailed(PURPOSE_NOT_CHANGEABLE)
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            users = UserRepository(session)
            consents = ConsentRepository(session)
            await _require_user(users, user_id)
            changed = await _apply_consent(
                consents, users, user_id=user_id, purpose=purpose, granted=granted, now=now
            )
            if changed:
                await AuditRepository(session).record(
                    actor_user_id=user_id,
                    action=CONSENT_CHANGE_ACTION,
                    target_type="consent",
                    target_id=user_id,
                    reason=f"{purpose}:{'granted' if granted else 'revoked'}",
                    created_at=now,
                )
            records = await consents.list_for_user(user_id)
        return _overview(records)

    async def export(self, user_id: UUID) -> DataExport:
        """Perfil, consentimentos e conversas, sem hashes nem ids de rastro. Seção 11.5."""
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            user = await _require_user(UserRepository(session), user_id)
            records = await ConsentRepository(session).list_for_user(user_id)
            conversations = ConversationRepository(session)
            exported: list[ExportedConversation] = []
            for conversation in reversed(await conversations.list_for_user(user_id)):
                messages = await conversations.list_messages(conversation.id)
                ratings = await conversations.feedback_ratings([item.id for item in messages])
                exported.append(
                    ExportedConversation(
                        id=conversation.id,
                        created_at=conversation.created_at,
                        messages=tuple(
                            ExportedMessage(
                                role=item.role,
                                content=item.content,
                                citations=tuple(
                                    ExportedCitation(
                                        index=citation.index,
                                        document_title=citation.document_title,
                                        heading=citation.heading,
                                    )
                                    for citation in item.citations
                                ),
                                outcome=item.outcome,
                                feedback=ratings.get(item.id),
                                created_at=item.created_at,
                            )
                            for item in messages
                        ),
                    )
                )
            data = DataExport(
                exported_at=now,
                email=user.email,
                full_name=user.full_name,
                phone=user.phone,
                visitor_type=user.visitor_type,
                visit_reason=user.visit_reason,
                role=user.role,
                created_at=user.created_at,
                consents=tuple(_consent_view(record) for record in records),
                conversations=tuple(exported),
            )
        return data

    async def delete_account(self, user_id: UUID) -> None:
        """Apaga tudo numa transação. A auditoria guarda só o id. Seção 11.6."""
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            users = UserRepository(session)
            user = await _require_user(users, user_id)
            if not delete_is_allowed(user.role):
                raise Forbidden(ADMIN_CANNOT_DELETE)
            await AuditRepository(session).record(
                actor_user_id=user_id,
                action=ACCOUNT_DELETE_ACTION,
                target_type="user",
                target_id=user_id,
                created_at=now,
            )
            await AuthSessionRepository(session).delete_for_user(user_id)
            await users.delete_user(user_id)


async def _apply_consent(
    consents: ConsentRepository,
    users: UserRepository,
    *,
    user_id: UUID,
    purpose: str,
    granted: bool,
    now: datetime,
) -> bool:
    if granted:
        if await consents.has_active(user_id, purpose, LEGAL_DOCUMENT_VERSION):
            return False
        await consents.insert_grants(
            user_id=user_id,
            grants=(ConsentGrant(purpose=purpose, document_version=LEGAL_DOCUMENT_VERSION),),
            source=ConsentSource.ACCOUNT.value,
            granted_at=now,
        )
        return True
    changed = await consents.revoke(user_id, purpose, now)
    if purpose == Purpose.PERSONALIZATION.value:
        await users.update_profile(user_id, dict.fromkeys(PERSONALIZED_FIELDS), now)
    return changed


async def _require_user(users: UserRepository, user_id: UUID) -> User:
    user = await users.get_by_id(user_id)
    if user is None:
        raise NotFound(USER_NOT_FOUND)
    return user


async def _profile(session: AsyncSession, user: User) -> Profile:
    current = await ConsentRepository(session).has_current_terms(user.id, LEGAL_DOCUMENT_VERSION)
    return Profile(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        visitor_type=user.visitor_type,
        visit_reason=user.visit_reason,
        role=user.role,
        needs_legal_acceptance=needs_legal_acceptance(LEGAL_DOCUMENT_VERSION if current else None),
    )


def _issue_message(field: str, code: str) -> str:
    if code == "personalization_required":
        return PERSONALIZATION_REQUIRED
    return message_for(field, code)


def _consent_view(record: ConsentRecord) -> ConsentView:
    return ConsentView(
        purpose=record.purpose,
        document_version=record.document_version,
        granted_at=record.granted_at,
        revoked_at=record.revoked_at,
        source=record.source,
    )


def _overview(records: list[ConsentRecord]) -> ConsentOverview:
    current: list[ConsentState] = []
    for purpose in _MANAGED_PURPOSES:
        active = [
            record for record in records if record.purpose == purpose and record.revoked_at is None
        ]
        latest = max(active, key=lambda record: record.granted_at, default=None)
        current.append(
            ConsentState(
                purpose=purpose,
                granted=latest is not None,
                document_version=None if latest is None else latest.document_version,
                granted_at=None if latest is None else latest.granted_at,
            )
        )
    return ConsentOverview(
        current=tuple(current),
        history=tuple(_consent_view(record) for record in reversed(records)),
    )
