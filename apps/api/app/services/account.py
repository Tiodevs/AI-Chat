"""Conta do membro: perfil, exportação, consentimentos e exclusão. Seções 11.5 e 11.6.

Camada de serviço. `controllers/account.py` autentica a sessão com
`AuthService.authenticate` e passa o id do usuário a `AccountService`, montado por pedido.
As rotas são `PATCH /v1/me`, `GET /v1/me/export`, `GET /v1/me/consents`,
`PUT /v1/me/consents/{purpose}` e `DELETE /v1/me` (seção 12).

Cada método é uma transação. Usa `UserRepository`, `ConsentRepository`,
`ConversationRepository`, `AuthSessionRepository` e `AuditRepository`, e as regras de
`domain/account.py`. Auditoria: `consent.change` e `account.delete` (seção 8.1).
"""

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

# As finalidades de `current`, nesta ordem, com ou sem concessão vigente (seção 8.1).
_MANAGED_PURPOSES = (
    Purpose.TERMS.value,
    Purpose.AGE.value,
    Purpose.PERSONALIZATION.value,
    Purpose.QUALITY.value,
)


@dataclass(frozen=True, slots=True)
class ConsentView:
    """Uma linha de `consent_records`. Revogar grava `revoked_at`; conceder cria outra."""

    purpose: str
    document_version: str
    granted_at: datetime
    revoked_at: datetime | None
    source: str


@dataclass(frozen=True, slots=True)
class ConsentState:
    """O estado vigente de uma finalidade: a concessão ativa mais recente, ou nenhuma."""

    purpose: str
    granted: bool
    document_version: str | None
    granted_at: datetime | None


@dataclass(frozen=True, slots=True)
class ConsentOverview:
    """Consentimentos da conta, como `GET /v1/me/consents` os devolve.

    `current` tem um item por finalidade. `history` tem todas as linhas, da mais nova à mais
    antiga.
    """

    current: tuple[ConsentState, ...]
    history: tuple[ConsentView, ...]


@dataclass(frozen=True, slots=True)
class ExportedCitation:
    """Citação na exportação: índice, título e seção. Sem id de chunk (seção 12)."""

    index: int
    document_title: str
    heading: str | None


@dataclass(frozen=True, slots=True)
class ExportedMessage:
    """Mensagem exportada, com o feedback dela. Sem modelo, tokens nem id de rastro."""

    role: str
    content: str
    citations: tuple[ExportedCitation, ...]
    outcome: str | None
    feedback: int | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ExportedConversation:
    """Conversa exportada com as mensagens na ordem em que foram gravadas."""

    id: UUID
    created_at: datetime
    messages: tuple[ExportedMessage, ...]


@dataclass(frozen=True, slots=True)
class DataExport:
    """A exportação da seção 11.5: perfil, consentimentos e conversas.

    Não tem hash de senha, id de rastro nem dado de outro titular.
    """

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
    """Direitos do titular exercidos pela própria conta (seção 11.5).

    Recebe o `user_id` já autenticado pelo controlador. Os métodos conferem de novo que o
    usuário existe e respondem 404 se ele sumiu depois da autenticação.
    """

    def __init__(self, *, database_url: str, clock: Clock) -> None:
        self._database_url = database_url
        self._clock = clock

    async def update_profile(self, user_id: UUID, changes: dict[str, str | None]) -> Profile:
        """Corrige o perfil. Só os campos enviados mudam, e `null` limpa um opcional.

        Numa transação: lê o usuário (404), confere se a personalização está ativa, valida no
        domínio (`plan_profile_update`) e grava. `visitor_type` e `visit_reason` exigem a
        personalização, e o e-mail não muda por aqui. Erros de campo respondem 422 em
        `field_errors`, sem gravar nada. Devolve o mesmo perfil de `GET /v1/me`.
        """
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
            # Relê a linha depois do `UPDATE`, para o perfil devolvido ser o que foi gravado.
            await session.refresh(user)
            profile = await _profile(session, user)
        return profile

    async def consents(self, user_id: UUID) -> ConsentOverview:
        """Consentimentos vigentes e o histórico com as versões, numa leitura."""
        async with open_session(self._database_url) as session, UnitOfWork(session):
            await _require_user(UserRepository(session), user_id)
            records = await ConsentRepository(session).list_for_user(user_id)
        return _overview(records)

    async def set_consent(self, user_id: UUID, purpose: str, *, granted: bool) -> ConsentOverview:
        """Concede ou revoga uma finalidade e grava `consent.change` quando algo mudou.

        1. Recusa com 422 a maioridade, finalidades desconhecidas e a revogação dos Termos.
           Aceitar `terms_and_privacy_notice` é como o membro aceita uma versão nova dos
           documentos (seção 11.11).
        2. Numa transação: concede com uma linha nova na versão vigente e `source = account`,
           ou revoga todas as concessões ativas. Revogar a personalização também apaga
           `visitor_type` e `visit_reason` na mesma transação (seção 12).
        3. Audita com o motivo `finalidade:granted` ou `finalidade:revoked`, só se mudou.
        """
        # 1.
        if not purpose_can_change(purpose, granted=granted):
            raise ValidationFailed(PURPOSE_NOT_CHANGEABLE)
        now = self._clock.now()
        # 2.
        async with open_session(self._database_url) as session, UnitOfWork(session):
            users = UserRepository(session)
            consents = ConsentRepository(session)
            await _require_user(users, user_id)
            changed = await _apply_consent(
                consents, users, user_id=user_id, purpose=purpose, granted=granted, now=now
            )
            # 3. O próprio membro é o ator. O alvo é o id dele, sem e-mail.
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
        """Perfil, consentimentos e conversas, sem hashes nem ids de rastro. Seção 11.5.

        Numa transação de leitura: o usuário (404), os consentimentos e, para cada conversa
        da mais antiga à mais nova, as mensagens e as notas de feedback (duas consultas por
        conversa). O controlador entrega o JSON como anexo.
        """
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            user = await _require_user(UserRepository(session), user_id)
            records = await ConsentRepository(session).list_for_user(user_id)
            conversations = ConversationRepository(session)
            exported: list[ExportedConversation] = []
            # `list_for_user` vem da mais nova à mais antiga; a exportação segue o tempo.
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
        """Apaga tudo numa transação. A auditoria guarda só o id. Seção 11.6.

        Um admin recebe 403 (seção 10.5). A ordem dentro da transação:

        1. Grava `account.delete`. `audit_events` não tem chave estrangeira para `users`,
           então o registro sobrevive à exclusão.
        2. Apaga as sessões de autenticação, cuja chave estrangeira não tem cascata. A
           seção 11.6 diz revogar; o código apaga.
        3. Apaga o usuário. Consentimentos, sessões de cadastro, conversas, mensagens e
           feedback saem pelo `ON DELETE CASCADE`, e o `user_id` dos pedidos de titular vira
           nulo.

        O controlador apaga o cookie de sessão.
        """
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            users = UserRepository(session)
            user = await _require_user(users, user_id)
            if not delete_is_allowed(user.role):
                raise Forbidden(ADMIN_CANNOT_DELETE)
            # 1.
            await AuditRepository(session).record(
                actor_user_id=user_id,
                action=ACCOUNT_DELETE_ACTION,
                target_type="user",
                target_id=user_id,
                created_at=now,
            )
            # 2.
            await AuthSessionRepository(session).delete_for_user(user_id)
            # 3.
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
    """Aplica a concessão ou a revogação na transação de quem chama. Devolve se mudou algo.

    Conceder de novo uma finalidade já ativa na versão vigente não cria linha. Revogar
    apaga os campos personalizados mesmo quando não havia concessão ativa.
    """
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
    # Sem personalização, tipo de visitante e motivo da visita não podem ficar gravados.
    if purpose == Purpose.PERSONALIZATION.value:
        await users.update_profile(user_id, dict.fromkeys(PERSONALIZED_FIELDS), now)
    return changed


async def _require_user(users: UserRepository, user_id: UUID) -> User:
    """O usuário do id, ou `NotFound` (404) se a conta não existe mais."""
    user = await users.get_by_id(user_id)
    if user is None:
        raise NotFound(USER_NOT_FOUND)
    return user


async def _profile(session: AsyncSession, user: User) -> Profile:
    """Perfil de `GET /v1/me`, com `needs_legal_acceptance` pela versão vigente dos Termos."""
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
    """Mensagem do erro de campo. As regras de campo são as do cadastro (seção 8.5)."""
    if code == "personalization_required":
        return PERSONALIZATION_REQUIRED
    return message_for(field, code)


def _consent_view(record: ConsentRecord) -> ConsentView:
    """Copia a linha do ORM num dataclass: o controlador não recebe a entidade do banco."""
    return ConsentView(
        purpose=record.purpose,
        document_version=record.document_version,
        granted_at=record.granted_at,
        revoked_at=record.revoked_at,
        source=record.source,
    )


def _overview(records: list[ConsentRecord]) -> ConsentOverview:
    """Estado vigente por finalidade e o histórico, da linha mais nova à mais antiga.

    `records` vem em ordem de concessão. A vigente de cada finalidade é a concessão sem
    `revoked_at` com o `granted_at` mais novo.
    """
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
