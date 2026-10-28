"""Cadastro por chat e por formulário. Os dois chamam a mesma conclusão. Seção 7.2."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.session_secret import new_session_secret
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.auth import (
    SESSION_MAX_AGE_SECONDS,
    SessionCookie,
    bucket_key,
    clean_user_agent,
    hash_session_secret,
    session_cookie,
)
from app.domain.errors import (
    Conflict,
    DomainError,
    NotFound,
    ProviderUnavailable,
    RateLimited,
    ValidationFailed,
)
from app.domain.fields import FieldIssue, password_is_acceptable, validate_field
from app.domain.legal import LEGAL_DOCUMENT_VERSION, needs_legal_acceptance
from app.domain.profile import Profile
from app.domain.registration import (
    MEMBER_ROLE,
    REGISTRATION_IP_PURPOSE,
    Acceptance,
    ConsentSource,
    FieldSet,
    FormValues,
    Machine,
    MemberDraft,
    Path,
    PublicFields,
    Status,
    TranscriptItem,
    accept_review,
    accepts_message,
    apply_edits,
    collect_form,
    completed_document,
    draft_member,
    dump_transcript,
    fields_document,
    load_transcript,
    machine_from_document,
    mark_password_set,
    new_machine,
    public_fields,
    registration_deadline,
    registration_rate_decision,
    registration_window_start,
    reject_review,
    session_is_expired,
    with_issue,
)
from app.ports.clock import Clock
from app.ports.password_hasher import PasswordHasher
from app.prompts.registration import (
    COMPLETION_FAILED,
    EMAIL_TAKEN,
    EXPIRED,
    GREETING,
    NOT_FOUND,
    RATE_LIMITED,
    REGISTRATION_UNAVAILABLE,
    WRONG_STEP,
    message_for,
    prompt_for,
)
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.consents import ConsentRepository
from app.repositories.conversations import ConversationRepository
from app.repositories.rate_limits import RateLimitRepository
from app.repositories.registration import RegistrationRecord, RegistrationRepository
from app.repositories.users import UserRepository
from app.workflows.registration import RegistrationWorkflow

PathName = Literal["chat", "form"]


@dataclass(frozen=True, slots=True)
class SessionView:
    id: UUID
    status: str
    path: PathName
    fields: PublicFields
    field_errors: dict[str, str]
    next_step: str
    prompt: str
    messages: tuple[TranscriptItem, ...]
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class Completion:
    profile: Profile
    cookie: SessionCookie


@dataclass(frozen=True, slots=True)
class FormInput:
    session_id: UUID | None
    full_name: str
    email: str
    phone: str | None
    visitor_type: str | None
    visit_reason: str | None
    password: str
    accept_terms: bool
    document_version: str
    age_18_plus: bool
    profile_personalization: bool
    quality_improvement: bool


class RegistrationService:
    def __init__(
        self,
        *,
        database_url: str,
        clock: Clock,
        hasher: PasswordHasher,
        hmac_key: str,
        app_env: str,
        workflow: RegistrationWorkflow,
    ) -> None:
        self._database_url = database_url
        self._clock = clock
        self._hasher = hasher
        self._hmac_key = hmac_key
        self._app_env = app_env
        self._workflow = workflow

    async def start(self) -> SessionView:
        now = self._clock.now()
        machine = new_machine()
        transcript = (TranscriptItem(role="assistant", text=GREETING, created_at=now),)
        async with open_session(self._database_url) as session, UnitOfWork(session):
            record = await RegistrationRepository(session).insert(
                session_id=uuid4(),
                status=machine.status.value,
                path=Path.CHAT.value,
                fields=fields_document(machine),
                password_hash=None,
                transcript=dump_transcript(transcript),
                user_id=None,
                expires_at=registration_deadline(now),
            )
        return _view(record, machine, GREETING)

    async def get(self, session_id: UUID) -> SessionView:
        record, machine = await self._open(session_id)
        return _view(record, machine, _stored_prompt(record, machine))

    async def message(
        self,
        session_id: UUID,
        text: str,
        *,
        request_id: str,
        client_ip: str,
    ) -> SessionView:
        await self._limit(client_ip)
        record, machine = await self._open(session_id)
        if not accepts_message(machine):
            raise ValidationFailed(WRONG_STEP)
        try:
            result = await self._workflow.turn(
                machine,
                text,
                request_id=request_id,
                email_taken=self._email_taken,
            )
        except ProviderUnavailable:
            raise ProviderUnavailable(REGISTRATION_UNAVAILABLE) from None
        now = self._clock.now()
        transcript = (
            *load_transcript(record.transcript),
            TranscriptItem(role="user", text=text, created_at=now),
            TranscriptItem(role="assistant", text=result.prompt, created_at=now),
        )
        saved = await self._save(record, result.machine, transcript, record.password_hash)
        return _view(saved, result.machine, result.prompt)

    async def patch_fields(self, session_id: UUID, edits: dict[str, str | None]) -> SessionView:
        record, machine = await self._open(session_id)
        if machine.status in (Status.COMPLETED, Status.ABANDONED):
            raise ValidationFailed(WRONG_STEP)
        updated = await self._edit(machine, edits)
        prompt = prompt_for(updated.next_step.value, correcting=updated.correcting)
        transcript = load_transcript(record.transcript)
        saved = await self._save(record, updated, transcript, record.password_hash)
        return _view(saved, updated, prompt)

    async def set_password(self, session_id: UUID, password: str, *, client_ip: str) -> SessionView:
        await self._limit(client_ip)
        record, machine = await self._open(session_id)
        if machine.status != Status.AWAITING_PASSWORD:
            raise ValidationFailed(WRONG_STEP)
        if not password_is_acceptable(password):
            invalid = replace(machine, field_errors=(FieldIssue("password", "invalid"),))
            saved = await self._save(
                record,
                invalid,
                load_transcript(record.transcript),
                record.password_hash,
            )
            prompt = prompt_for(invalid.next_step.value, correcting=False)
            return _view(saved, invalid, prompt)
        digest = self._hasher.hash_password(password)
        updated = mark_password_set(machine)
        if updated is None:
            raise ValidationFailed(WRONG_STEP)
        prompt = prompt_for(updated.next_step.value, correcting=False)
        now = self._clock.now()
        transcript = (
            *load_transcript(record.transcript),
            TranscriptItem(role="assistant", text=prompt, created_at=now),
        )
        saved = await self._save(record, updated, transcript, digest)
        return _view(saved, updated, prompt)

    async def review(self, session_id: UUID, *, accept: bool) -> SessionView:
        record, machine = await self._open(session_id)
        updated = accept_review(machine) if accept else reject_review(machine)
        if updated is None:
            raise ValidationFailed(WRONG_STEP)
        prompt = prompt_for(updated.next_step.value, correcting=updated.correcting)
        now = self._clock.now()
        transcript = (
            *load_transcript(record.transcript),
            TranscriptItem(role="assistant", text=prompt, created_at=now),
        )
        saved = await self._save(record, updated, transcript, record.password_hash)
        return _view(saved, updated, prompt)

    async def accept(
        self,
        session_id: UUID,
        acceptance: Acceptance,
        *,
        user_agent: str,
        guest_secret: str | None,
    ) -> Completion:
        now = self._clock.now()
        try:
            error, result = await self._accept_locked(
                session_id,
                acceptance,
                user_agent=user_agent,
                guest_secret=guest_secret,
                now=now,
            )
        except IntegrityError:
            raise Conflict(EMAIL_TAKEN, field_errors={"email": EMAIL_TAKEN}) from None
        if error is not None:
            raise error
        if result is None:
            raise NotFound(NOT_FOUND)
        return result

    async def submit_form(
        self,
        form: FormInput,
        *,
        user_agent: str,
        guest_secret: str | None,
        client_ip: str,
    ) -> Completion:
        await self._limit(client_ip)
        if form.session_id is not None:
            existing, _machine = await self._open(form.session_id)
            if existing.status == Status.COMPLETED.value and existing.user_id is not None:
                return await self._reissue_standalone(existing.user_id, user_agent)
        draft = _draft_from_form(form)
        if await self._email_taken(draft.email):
            raise Conflict(EMAIL_TAKEN, field_errors={"email": EMAIL_TAKEN})
        digest = self._hasher.hash_password(form.password)
        now = self._clock.now()
        if form.session_id is None:
            return await self._finish_new_form(
                draft,
                digest,
                user_agent=user_agent,
                guest_secret=guest_secret,
                now=now,
            )
        return await self._finish_form_session(
            form.session_id,
            draft,
            digest,
            user_agent=user_agent,
            guest_secret=guest_secret,
            now=now,
        )

    async def _accept_locked(
        self,
        session_id: UUID,
        acceptance: Acceptance,
        *,
        user_agent: str,
        guest_secret: str | None,
        now: datetime,
    ) -> tuple[DomainError | None, Completion | None]:
        async with open_session(self._database_url) as session, UnitOfWork(session):
            current = await RegistrationRepository(session).lock(session_id)
            if current is None:
                return NotFound(NOT_FOUND), None
            if current.status == Status.COMPLETED.value and current.user_id is not None:
                return None, await self._reissue(session, current.user_id, user_agent, now)
            closed = await _close_if_needed(session, current, now)
            if closed is not None:
                return closed, None
            if current.status != Status.AWAITING_ACCEPTANCE.value:
                return ValidationFailed(WRONG_STEP), None
            machine = machine_from_document(
                current.status,
                current.fields,
                password_set=current.password_hash is not None,
            )
            return await self._finish_record(
                session,
                current,
                acceptance=acceptance,
                source=ConsentSource.CHAT.value,
                password_hash=current.password_hash,
                fields=machine.fields,
                user_agent=user_agent,
                guest_secret=guest_secret,
                now=now,
            )
        raise RuntimeError("registration session")

    async def _finish_record(
        self,
        session: AsyncSession,
        current: RegistrationRecord,
        *,
        acceptance: Acceptance,
        source: str,
        password_hash: str | None,
        fields: FieldSet,
        user_agent: str,
        guest_secret: str | None,
        now: datetime,
    ) -> tuple[DomainError | None, Completion | None]:
        draft = draft_member(
            fields,
            acceptance,
            expected_version=LEGAL_DOCUMENT_VERSION,
            password_ready=password_hash is not None,
        )
        if not isinstance(draft, MemberDraft):
            return ValidationFailed(COMPLETION_FAILED, field_errors=_messages(draft)), None
        if password_hash is None:
            missing = (FieldIssue("password", "required"),)
            return ValidationFailed(COMPLETION_FAILED, field_errors=_messages(missing)), None
        if await UserRepository(session).get_by_email(draft.email) is not None:
            return Conflict(EMAIL_TAKEN, field_errors={"email": EMAIL_TAKEN}), None
        result = await self._create_member(
            session,
            draft=draft,
            password_hash=password_hash,
            source=source,
            user_agent=user_agent,
            guest_secret=guest_secret,
            now=now,
        )
        await RegistrationRepository(session).save(_completed(current, draft, result.profile.id))
        return None, result

    async def _finish_new_form(
        self,
        draft: MemberDraft,
        password_hash: str,
        *,
        user_agent: str,
        guest_secret: str | None,
        now: datetime,
    ) -> Completion:
        error: DomainError | None = None
        result: Completion | None = None
        try:
            async with open_session(self._database_url) as session, UnitOfWork(session):
                if await UserRepository(session).get_by_email(draft.email) is not None:
                    error = Conflict(EMAIL_TAKEN, field_errors={"email": EMAIL_TAKEN})
                else:
                    result = await self._create_member(
                        session,
                        draft=draft,
                        password_hash=password_hash,
                        source=ConsentSource.FORM.value,
                        user_agent=user_agent,
                        guest_secret=guest_secret,
                        now=now,
                    )
                    await RegistrationRepository(session).insert(
                        session_id=uuid4(),
                        status=Status.COMPLETED.value,
                        path=Path.FORM.value,
                        fields=completed_document(draft),
                        password_hash=None,
                        transcript=[],
                        user_id=result.profile.id,
                        expires_at=registration_deadline(now),
                    )
        except IntegrityError:
            raise Conflict(EMAIL_TAKEN, field_errors={"email": EMAIL_TAKEN}) from None
        if error is not None:
            raise error
        if result is None:
            raise NotFound(NOT_FOUND)
        return result

    async def _finish_form_session(
        self,
        session_id: UUID,
        draft: MemberDraft,
        password_hash: str,
        *,
        user_agent: str,
        guest_secret: str | None,
        now: datetime,
    ) -> Completion:
        error: DomainError | None = None
        result: Completion | None = None
        try:
            async with open_session(self._database_url) as session, UnitOfWork(session):
                current = await RegistrationRepository(session).lock(session_id)
                if current is None:
                    error = NotFound(NOT_FOUND)
                elif current.status == Status.COMPLETED.value and current.user_id is not None:
                    result = await self._reissue(session, current.user_id, user_agent, now)
                else:
                    closed = await _close_if_needed(session, current, now)
                    if closed is not None:
                        error = closed
                    elif await UserRepository(session).get_by_email(draft.email) is not None:
                        error = Conflict(EMAIL_TAKEN, field_errors={"email": EMAIL_TAKEN})
                    else:
                        result = await self._create_member(
                            session,
                            draft=draft,
                            password_hash=password_hash,
                            source=ConsentSource.FORM.value,
                            user_agent=user_agent,
                            guest_secret=guest_secret,
                            now=now,
                        )
                        await RegistrationRepository(session).save(
                            _completed(current, draft, result.profile.id)
                        )
        except IntegrityError:
            raise Conflict(EMAIL_TAKEN, field_errors={"email": EMAIL_TAKEN}) from None
        if error is not None:
            raise error
        if result is None:
            raise NotFound(NOT_FOUND)
        return result

    async def _create_member(
        self,
        session: AsyncSession,
        *,
        draft: MemberDraft,
        password_hash: str,
        source: str,
        user_agent: str,
        guest_secret: str | None,
        now: datetime,
    ) -> Completion:
        user_id = await UserRepository(session).insert(
            email=draft.email,
            password_hash=password_hash,
            full_name=draft.full_name,
            role=MEMBER_ROLE,
            now=now,
            phone=draft.phone,
            visitor_type=draft.visitor_type,
            visit_reason=draft.visit_reason,
        )
        await ConsentRepository(session).insert_grants(
            user_id=user_id,
            grants=draft.consents,
            source=source,
            granted_at=now,
        )
        guest_id = await _guest_id(session, guest_secret)
        if guest_id is not None:
            await ConversationRepository(session).attach_to_user(
                guest_key_id=guest_id,
                user_id=user_id,
            )
        return Completion(
            profile=Profile(
                id=user_id,
                email=draft.email,
                full_name=draft.full_name,
                phone=draft.phone,
                visitor_type=draft.visitor_type,
                visit_reason=draft.visit_reason,
                role=MEMBER_ROLE,
                needs_legal_acceptance=False,
            ),
            cookie=await self._open_auth(session, user_id, user_agent, now),
        )

    async def _reissue_standalone(self, user_id: UUID, user_agent: str) -> Completion:
        async with open_session(self._database_url) as session, UnitOfWork(session):
            return await self._reissue(session, user_id, user_agent, self._clock.now())
        raise RuntimeError("registration session")

    async def _reissue(
        self,
        session: AsyncSession,
        user_id: UUID,
        user_agent: str,
        now: datetime,
    ) -> Completion:
        user = await UserRepository(session).get_by_id(user_id)
        if user is None:
            raise NotFound(NOT_FOUND)
        version = None
        if await ConsentRepository(session).has_current_terms(user_id, LEGAL_DOCUMENT_VERSION):
            version = LEGAL_DOCUMENT_VERSION
        return Completion(
            profile=Profile(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                phone=user.phone,
                visitor_type=user.visitor_type,
                visit_reason=user.visit_reason,
                role=user.role,
                needs_legal_acceptance=needs_legal_acceptance(version),
            ),
            cookie=await self._open_auth(session, user_id, user_agent, now),
        )

    async def _open_auth(
        self,
        session: AsyncSession,
        user_id: UUID,
        user_agent: str,
        now: datetime,
    ) -> SessionCookie:
        secret = new_session_secret()
        await AuthSessionRepository(session).create(
            token_hash=hash_session_secret(secret),
            user_id=user_id,
            expires_at=now + timedelta(seconds=SESSION_MAX_AGE_SECONDS),
            user_agent=clean_user_agent(user_agent),
        )
        return session_cookie(secret=secret, app_env=self._app_env)

    async def _open(self, session_id: UUID) -> tuple[RegistrationRecord, Machine]:
        now = self._clock.now()
        error: DomainError | None = None
        record: RegistrationRecord | None = None
        async with open_session(self._database_url) as session, UnitOfWork(session):
            current = await RegistrationRepository(session).get(session_id)
            if current is None:
                error = NotFound(NOT_FOUND)
            else:
                closed = await _close_if_needed(session, current, now)
                if closed is not None:
                    error = closed
                else:
                    record = current
        if error is not None:
            raise error
        if record is None:
            raise NotFound(NOT_FOUND)
        return record, _machine(record)

    async def _save(
        self,
        record: RegistrationRecord,
        machine: Machine,
        transcript: tuple[TranscriptItem, ...],
        password_hash: str | None,
    ) -> RegistrationRecord:
        now = self._clock.now()
        error: DomainError | None = None
        saved: RegistrationRecord | None = None
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repo = RegistrationRepository(session)
            current = await repo.lock(record.id)
            if current is None:
                error = NotFound(NOT_FOUND)
            else:
                closed = await _close_if_needed(session, current, now)
                if closed is not None:
                    error = closed
                elif current.status != record.status:
                    error = ValidationFailed(WRONG_STEP)
                else:
                    saved = await repo.save(
                        replace(
                            current,
                            status=machine.status.value,
                            fields=fields_document(machine),
                            password_hash=password_hash,
                            transcript=dump_transcript(transcript),
                        )
                    )
        if error is not None:
            raise error
        if saved is None:
            raise NotFound(NOT_FOUND)
        return saved

    async def _edit(self, machine: Machine, edits: dict[str, str | None]) -> Machine:
        remaining = dict(edits)
        taken = False
        raw_email = remaining.get("email")
        if isinstance(raw_email, str) and raw_email.strip():
            normalized, issue = validate_field("email", raw_email)
            if issue is None and normalized is not None and await self._email_taken(normalized):
                taken = True
                remaining.pop("email")
        updated = apply_edits(machine, remaining)
        if taken:
            return with_issue(updated, FieldIssue("email", "taken"))
        return updated

    async def _limit(self, client_ip: str) -> None:
        if not self._hmac_key:
            raise RuntimeError("RATE_LIMIT_HMAC_KEY vazio.")
        now = self._clock.now()
        window = registration_window_start(now)
        key = bucket_key(
            purpose=REGISTRATION_IP_PURPOSE,
            subject=client_ip,
            day=now.astimezone(UTC).date(),
            key=self._hmac_key,
        )
        async with open_session(self._database_url) as session, UnitOfWork(session):
            count = await RateLimitRepository(session).increment(key, window)
            decision = registration_rate_decision(count=count, now=now, window_start=window)
        if decision.limited:
            raise RateLimited(RATE_LIMITED, retry_after_seconds=decision.retry_after_seconds)

    async def _email_taken(self, email: str) -> bool:
        async with open_session(self._database_url) as session, UnitOfWork(session):
            return await UserRepository(session).get_by_email(email) is not None
        raise RuntimeError("registration session")


def _draft_from_form(form: FormInput) -> MemberDraft:
    fields, issues = collect_form(
        FormValues(
            full_name=form.full_name,
            email=form.email,
            phone=form.phone,
            visitor_type=form.visitor_type,
            visit_reason=form.visit_reason,
        )
    )
    if not password_is_acceptable(form.password):
        issues = (*issues, FieldIssue("password", "invalid"))
    if issues:
        raise ValidationFailed(COMPLETION_FAILED, field_errors=_messages(issues))
    draft = draft_member(
        fields,
        Acceptance(
            accept_terms=form.accept_terms,
            document_version=form.document_version,
            age_18_plus=form.age_18_plus,
            profile_personalization=form.profile_personalization,
            quality_improvement=form.quality_improvement,
        ),
        expected_version=LEGAL_DOCUMENT_VERSION,
        password_ready=True,
    )
    if not isinstance(draft, MemberDraft):
        raise ValidationFailed(COMPLETION_FAILED, field_errors=_messages(draft))
    return draft


def _view(record: RegistrationRecord, machine: Machine, prompt: str) -> SessionView:
    return SessionView(
        id=record.id,
        status=machine.status.value,
        path=_path(record.path),
        fields=public_fields(machine.fields),
        field_errors=_messages(machine.field_errors),
        next_step=machine.next_step.value,
        prompt=prompt,
        messages=load_transcript(record.transcript),
        expires_at=record.expires_at,
    )


def _stored_prompt(record: RegistrationRecord, machine: Machine) -> str:
    for item in reversed(load_transcript(record.transcript)):
        if item.role == "assistant":
            return item.text
    return prompt_for(machine.next_step.value, correcting=machine.correcting)


def _messages(issues: tuple[FieldIssue, ...]) -> dict[str, str]:
    return {issue.field: message_for(issue.field, issue.code) for issue in issues}


def _machine(record: RegistrationRecord) -> Machine:
    return machine_from_document(
        record.status,
        record.fields,
        password_set=record.password_hash is not None,
    )


def _completed(record: RegistrationRecord, draft: MemberDraft, user_id: UUID) -> RegistrationRecord:
    return replace(
        record,
        status=Status.COMPLETED.value,
        fields=completed_document(draft),
        password_hash=None,
        transcript=[],
        user_id=user_id,
    )


def _abandoned(record: RegistrationRecord) -> RegistrationRecord:
    return replace(record, status=Status.ABANDONED.value, password_hash=None, transcript=[])


async def _close_if_needed(
    session: AsyncSession,
    record: RegistrationRecord,
    now: datetime,
) -> DomainError | None:
    if record.status == Status.ABANDONED.value:
        return ValidationFailed(EXPIRED)
    if not session_is_expired(status=record.status, expires_at=record.expires_at, now=now):
        return None
    await RegistrationRepository(session).save(_abandoned(record))
    return ValidationFailed(EXPIRED)


def _path(value: str) -> PathName:
    if value == Path.FORM.value:
        return "form"
    if value == Path.CHAT.value:
        return "chat"
    raise RuntimeError("registration path")


async def _guest_id(session: AsyncSession, secret: str | None) -> UUID | None:
    if not secret:
        return None
    found = await ConversationRepository(session).get_guest_key_by_hash(hash_session_secret(secret))
    if found is None:
        return None
    return found.id
