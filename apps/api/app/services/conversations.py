"""Conversas por HTTP: duas transações curtas e o fluxo SSE. Seções 6.4 e 7.1."""

import asyncio
import contextlib
import time
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.session_secret import new_session_secret
from app.core.sse import (
    DISCONNECTED,
    KEEPALIVE,
    KEEPALIVE_COMMENT,
    SSE_KEEPALIVE_SECONDS,
    next_stream_item,
)
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.auth import (
    RateDecision,
    SessionCookie,
    bucket_key,
    fixed_window_start,
    hash_session_secret,
)
from app.domain.errors import (
    Conflict,
    DuplicateMessage,
    Forbidden,
    NotFound,
    RateLimited,
    Unauthenticated,
    ValidationFailed,
)
from app.domain.grounding import Citation
from app.domain.outcomes import Outcome
from app.domain.questions import (
    DIAGNOSTICS_IP_PURPOSE,
    DIAGNOSTICS_WINDOW,
    MAX_QUESTION_CHARS,
    QUESTION_GUEST_IP_PURPOSE,
    QUESTION_GUEST_KEY_PURPOSE,
    QUESTION_MEMBER_PURPOSE,
    QUESTION_WINDOW,
    diagnostics_rate_decision,
    guest_cookie,
    guest_question_rate_decision,
    member_question_rate_decision,
    owns_conversation,
    stored_user_content,
)
from app.ports.budget import TokenBudget
from app.ports.clock import Clock
from app.prompts.auth import UNAUTHENTICATED, VALIDATION
from app.prompts.conversations import (
    CONVERSATION_NOT_FOUND,
    DIAGNOSTICS_RATE_LIMITED,
    DUPLICATE_FEEDBACK,
    DUPLICATE_MESSAGE,
    FEEDBACK_NOT_ASSISTANT,
    MESSAGE_NOT_FOUND,
    NOT_OWNER,
    RATE_LIMITED,
    STREAM_FAILED,
)
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.conversations import (
    ConversationRecord,
    ConversationRepository,
    DuplicateClientMessage,
    MessageRecord,
)
from app.repositories.rate_limits import RateLimitRepository
from app.services.conversation_events import (
    AskEvent,
    CitationEvent,
    CommentEvent,
    DoneEvent,
    ErrorEvent,
    MetaEvent,
    ReplaceEvent,
    TokenEvent,
)
from app.workflows.qa import ConversationTurn, QaResult, QaWorkflow, degraded_result, error_result

_STOP = object()


@dataclass(frozen=True, slots=True)
class PreparedQuestion:
    conversation_id: UUID
    text: str
    client_message_id: UUID
    history: tuple[ConversationTurn, ...]
    budget_exceeded: bool
    request_id: str
    assistant_message_id: UUID


@dataclass(frozen=True, slots=True)
class _Actor:
    user_id: UUID | None
    guest_key_id: UUID | None


class ConversationService:
    def __init__(
        self,
        *,
        database_url: str,
        clock: Clock,
        hmac_key: str,
        app_env: str,
        workflow: QaWorkflow,
        budget: TokenBudget,
    ) -> None:
        self._database_url = database_url
        self._clock = clock
        self._hmac_key = hmac_key
        self._app_env = app_env
        self._workflow = workflow
        self._budget = budget

    async def create(
        self,
        *,
        session_secret: str | None,
        guest_secret: str | None,
    ) -> tuple[ConversationRecord, SessionCookie | None]:
        now = self._clock.now()
        if session_secret:
            user_id = await self._lookup_user(session_secret)
            if user_id is None:
                raise Unauthenticated(UNAUTHENTICATED)
            async with open_session(self._database_url) as session, UnitOfWork(session):
                repository = ConversationRepository(session)
                record = await repository.insert_conversation(
                    user_id=user_id,
                    guest_key_id=None,
                    created_at=await repository.allocate_conversation_created_at(now),
                )
            return record, None

        guest_id, cookie = await self._ensure_guest(guest_secret)
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = ConversationRepository(session)
            record = await repository.insert_conversation(
                user_id=None,
                guest_key_id=guest_id,
                created_at=await repository.allocate_conversation_created_at(now),
            )
        return record, cookie

    async def list_for_member(self, session_secret: str | None) -> list[ConversationRecord]:
        if not session_secret:
            raise Unauthenticated(UNAUTHENTICATED)
        user_id = await self._lookup_user(session_secret)
        if user_id is None:
            raise Unauthenticated(UNAUTHENTICATED)
        async with open_session(self._database_url) as session, UnitOfWork(session):
            records = await ConversationRepository(session).list_for_user(user_id)
        return records

    async def get(
        self,
        conversation_id: UUID,
        *,
        session_secret: str | None,
        guest_secret: str | None,
    ) -> tuple[ConversationRecord, list[MessageRecord]]:
        actor = await self._actor(session_secret, guest_secret)
        conversation: ConversationRecord | None
        messages: list[MessageRecord]
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = ConversationRepository(session)
            conversation = await repository.get_conversation(conversation_id)
            messages = []
            if conversation is not None:
                messages = await repository.list_messages(conversation_id)
        if conversation is None:
            raise NotFound(CONVERSATION_NOT_FOUND)
        if not _owns(actor, conversation):
            raise Forbidden(NOT_OWNER)
        return conversation, messages

    async def prepare_ask(
        self,
        conversation_id: UUID,
        *,
        text: str,
        client_message_id: UUID,
        session_secret: str | None,
        guest_secret: str | None,
        client_ip: str,
        request_id: str,
    ) -> PreparedQuestion:
        if not text or len(text) > MAX_QUESTION_CHARS:
            raise ValidationFailed(VALIDATION)
        self._require_hmac()
        actor = await self._actor(session_secret, guest_secret)
        now = self._clock.now()
        existing_id: UUID | None = None
        history: tuple[ConversationTurn, ...] = ()
        limited = False
        retry_after = 0
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = ConversationRepository(session)
            conversation = await repository.get_conversation(conversation_id)
            if conversation is None:
                raise NotFound(CONVERSATION_NOT_FOUND)
            if not _owns(actor, conversation):
                raise Forbidden(NOT_OWNER)
            existing = await repository.find_user_message(conversation_id, client_message_id)
            if existing is not None:
                existing_id = existing.id
            else:
                decision = await self._consume_question_rate(session, actor, client_ip, now)
                limited = decision.limited
                retry_after = decision.retry_after_seconds
                history = _turns(await repository.list_messages(conversation_id))
        if existing_id is not None:
            raise DuplicateMessage(DUPLICATE_MESSAGE, message_id=existing_id)
        if limited:
            raise RateLimited(RATE_LIMITED, retry_after_seconds=retry_after)
        return PreparedQuestion(
            conversation_id=conversation_id,
            text=text,
            client_message_id=client_message_id,
            history=history,
            budget_exceeded=await self._budget.exceeded(),
            request_id=request_id,
            assistant_message_id=uuid4(),
        )

    def stream(
        self,
        prepared: PreparedQuestion,
        disconnected: asyncio.Event,
    ) -> AsyncIterator[AskEvent]:
        return _AskStream(self, prepared, disconnected).events()

    async def submit_feedback(
        self,
        message_id: UUID,
        rating: int,
        *,
        session_secret: str | None,
        guest_secret: str | None,
    ) -> None:
        actor = await self._actor(session_secret, guest_secret)
        try:
            async with open_session(self._database_url) as session, UnitOfWork(session):
                repository = ConversationRepository(session)
                message = await repository.get_message(message_id)
                if message is None:
                    raise NotFound(MESSAGE_NOT_FOUND)
                conversation = await repository.get_conversation(message.conversation_id)
                if conversation is None or not _owns(actor, conversation):
                    raise Forbidden(NOT_OWNER)
                if message.role != "assistant":
                    raise ValidationFailed(FEEDBACK_NOT_ASSISTANT)
                await repository.insert_feedback(message_id, rating, self._clock.now())
        except IntegrityError:
            raise Conflict(DUPLICATE_FEEDBACK) from None

    async def prepare_diagnostics(self, client_ip: str) -> None:
        self._require_hmac()
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            day = now.astimezone(UTC).date()
            window = fixed_window_start(now, DIAGNOSTICS_WINDOW)
            count = await RateLimitRepository(session).increment(
                bucket_key(
                    purpose=DIAGNOSTICS_IP_PURPOSE,
                    subject=client_ip,
                    day=day,
                    key=self._hmac_key,
                ),
                window,
            )
            decision = diagnostics_rate_decision(ip_count=count, now=now, window_start=window)
        if decision.limited:
            raise RateLimited(
                DIAGNOSTICS_RATE_LIMITED,
                retry_after_seconds=decision.retry_after_seconds,
            )

    async def _actor(self, session_secret: str | None, guest_secret: str | None) -> _Actor:
        user_id = None
        if session_secret:
            user_id = await self._lookup_user(session_secret)
            if user_id is None:
                raise Unauthenticated(UNAUTHENTICATED)
        guest_id = await self._lookup_guest(guest_secret) if guest_secret else None
        if user_id is None and guest_id is None:
            raise Unauthenticated(UNAUTHENTICATED)
        return _Actor(user_id=user_id, guest_key_id=guest_id)

    async def _lookup_user(self, secret: str) -> UUID | None:
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            sessions = AuthSessionRepository(session)
            found = await sessions.get_active(hash_session_secret(secret), now)
        if found is None:
            return None
        return found.user_id

    async def _lookup_guest(self, secret: str) -> UUID | None:
        async with open_session(self._database_url) as session, UnitOfWork(session):
            found = await ConversationRepository(session).get_guest_key_by_hash(
                hash_session_secret(secret)
            )
        if found is None:
            return None
        return found.id

    async def _ensure_guest(self, secret: str | None) -> tuple[UUID, SessionCookie | None]:
        if secret:
            guest_id = await self._lookup_guest(secret)
            if guest_id is not None:
                return guest_id, None
        created_secret = new_session_secret()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            created = await ConversationRepository(session).insert_guest_key(
                hash_session_secret(created_secret),
                self._clock.now(),
            )
        return created.id, guest_cookie(secret=created_secret, app_env=self._app_env)

    async def _consume_question_rate(
        self,
        session: AsyncSession,
        actor: _Actor,
        client_ip: str,
        now: datetime,
    ) -> RateDecision:
        rates = RateLimitRepository(session)
        day = now.astimezone(UTC).date()
        window = fixed_window_start(now, QUESTION_WINDOW)
        if actor.user_id is not None:
            count = await rates.increment(
                bucket_key(
                    purpose=QUESTION_MEMBER_PURPOSE,
                    subject=str(actor.user_id),
                    day=day,
                    key=self._hmac_key,
                ),
                window,
            )
            return member_question_rate_decision(user_count=count, now=now, window_start=window)
        if actor.guest_key_id is None:
            raise Unauthenticated(UNAUTHENTICATED)
        key_count = await rates.increment(
            bucket_key(
                purpose=QUESTION_GUEST_KEY_PURPOSE,
                subject=str(actor.guest_key_id),
                day=day,
                key=self._hmac_key,
            ),
            window,
        )
        ip_count = await rates.increment(
            bucket_key(
                purpose=QUESTION_GUEST_IP_PURPOSE,
                subject=client_ip,
                day=day,
                key=self._hmac_key,
            ),
            window,
        )
        return guest_question_rate_decision(
            key_count=key_count,
            ip_count=ip_count,
            now=now,
            window_start=window,
        )

    def _require_hmac(self) -> None:
        if not self._hmac_key:
            raise RuntimeError("RATE_LIMIT_HMAC_KEY vazio.")


def _owns(actor: _Actor, conversation: ConversationRecord) -> bool:
    return owns_conversation(
        actor_user_id=actor.user_id,
        actor_guest_key_id=actor.guest_key_id,
        owner_user_id=conversation.user_id,
        owner_guest_key_id=conversation.guest_key_id,
    )


def _turns(rows: Sequence[MessageRecord]) -> tuple[ConversationTurn, ...]:
    turns: list[ConversationTurn] = []
    for row in rows:
        if row.role == "user":
            turns.append(ConversationTurn(role="user", content=row.content))
        elif row.role == "assistant":
            turns.append(ConversationTurn(role="assistant", content=row.content))
    return tuple(turns)


class _Sink:
    def __init__(self, stream: "_AskStream") -> None:
        self._stream = stream

    async def classified(self, intent: str) -> None:
        await self._stream.save_user(intent)

    async def token(self, text: str) -> None:
        self._stream.tokens_seen += 1
        await self._stream.queue.put(text)


class _AskStream:
    def __init__(
        self,
        service: ConversationService,
        prepared: PreparedQuestion,
        disconnected: asyncio.Event,
    ) -> None:
        self._service = service
        self._prepared = prepared
        self._disconnected = disconnected
        self.queue: asyncio.Queue[object] = asyncio.Queue()
        self.tokens_seen = 0
        self._lock = asyncio.Lock()
        self._user_lock = asyncio.Lock()
        self._user_saved = False
        self._duplicate = False
        self._stored = False
        self._result: QaResult | None = None
        self._error: BaseException | None = None
        self._started = time.perf_counter()

    async def events(self) -> AsyncIterator[AskEvent]:
        task: asyncio.Task[None] | None = None
        try:
            if self._prepared.budget_exceeded:
                self._result = degraded_result(self._prepared.assistant_message_id)
                await self._finish()
            yield MetaEvent(self._prepared.assistant_message_id, self._prepared.request_id)
            if self._prepared.budget_exceeded and self._result is not None:
                yield TokenEvent(self._result.text)
                yield DoneEvent(self._result.outcome.value)
                return
            task = asyncio.create_task(self._execute())
            while True:
                item = await next_stream_item(
                    self.queue,
                    self._disconnected,
                    interval_seconds=SSE_KEEPALIVE_SECONDS,
                )
                if item is DISCONNECTED:
                    return
                if item is KEEPALIVE:
                    yield CommentEvent(KEEPALIVE_COMMENT)
                    continue
                if item is _STOP:
                    break
                if isinstance(item, str):
                    yield TokenEvent(item)
            if task is not None:
                await task
                task = None
            if self._duplicate or isinstance(self._error, DuplicateClientMessage):
                self._stored = True
                yield ErrorEvent("conflict", DUPLICATE_MESSAGE)
                return
            if self._error is not None or self._result is None:
                self._result = error_result(self._prepared.assistant_message_id)
                await self._finish()
                yield ErrorEvent("error", STREAM_FAILED)
                return
            await self._finish()
            result = self._result
            if self.tokens_seen and result.outcome is Outcome.GROUNDING_FAILED:
                yield ReplaceEvent(result.text, "grounding_failed")
            elif self.tokens_seen == 0 and result.text:
                yield TokenEvent(result.text)
            for citation in result.citations:
                yield CitationEvent(
                    index=citation.index,
                    document_title=citation.document_title,
                    heading=citation.heading,
                    chunk_id=citation.chunk_id,
                )
            yield DoneEvent(result.outcome.value)
        finally:
            await asyncio.shield(self._stop(task))

    async def _execute(self) -> None:
        try:
            self._result = await self._service._workflow.run(
                self._prepared.text,
                history=self._prepared.history,
                visitor_type=None,
                request_id=self._prepared.request_id,
                run_id=self._prepared.assistant_message_id,
                events=_Sink(self),
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._error = exc
            if not isinstance(exc, DuplicateClientMessage):
                structlog.get_logger("atrium").warning(
                    "question.failed",
                    error_type=type(exc).__name__,
                )
        finally:
            self.queue.put_nowait(_STOP)

    async def save_user(self, intent: str | None) -> None:
        async with self._user_lock:
            if self._user_saved or self._duplicate:
                return
            content = stored_user_content(intent=intent, text=self._prepared.text)
            message_id = uuid4()
            try:
                async with (
                    open_session(self._service._database_url) as session,
                    UnitOfWork(session),
                ):
                    repository = ConversationRepository(session)
                    created_at = await repository.allocate_created_at(
                        self._prepared.conversation_id,
                        self._service._clock.now(),
                    )
                    await repository.insert_message(
                        message_id=message_id,
                        conversation_id=self._prepared.conversation_id,
                        client_message_id=self._prepared.client_message_id,
                        role="user",
                        content=content,
                        citations=(),
                        model=None,
                        prompt_version=None,
                        input_tokens=0,
                        output_tokens=0,
                        latency_ms=None,
                        outcome=None,
                        langsmith_run_id=None,
                        created_at=created_at,
                    )
            except IntegrityError:
                existing = await self._existing_user_message()
                if existing is None:
                    raise
                self._duplicate = True
                raise DuplicateClientMessage(existing.id) from None
            self._user_saved = True

    async def _finish(self) -> None:
        tokens = (0, 0)
        async with self._lock:
            if self._stored or self._duplicate:
                self._stored = True
                return
            result = self._result
            try:
                await self.save_user(None if result is None else result.intent)
            except DuplicateClientMessage as exc:
                self._error = exc
                self._stored = True
                return
            await self._save_assistant(result)
            self._stored = True
            if result is not None:
                tokens = (result.input_tokens, result.output_tokens)
        await self._service._budget.record(tokens[0], tokens[1])

    async def _save_assistant(self, result: QaResult | None) -> None:
        if result is None:
            outcome = Outcome.CANCELLED.value
            text = ""
            citations: tuple[Citation, ...] = ()
            model = None
            prompt_version = None
            input_tokens = 0
            output_tokens = 0
        else:
            outcome = result.outcome.value
            text = result.text
            citations = result.citations
            model = result.model
            prompt_version = result.prompt_version
            input_tokens = result.input_tokens
            output_tokens = result.output_tokens
        latency_ms = max(0, int((time.perf_counter() - self._started) * 1000))
        try:
            async with (
                open_session(self._service._database_url) as session,
                UnitOfWork(session),
            ):
                repository = ConversationRepository(session)
                created_at = await repository.allocate_created_at(
                    self._prepared.conversation_id,
                    self._service._clock.now(),
                )
                await repository.insert_message(
                    message_id=self._prepared.assistant_message_id,
                    conversation_id=self._prepared.conversation_id,
                    client_message_id=None,
                    role="assistant",
                    content=text,
                    citations=citations,
                    model=model,
                    prompt_version=prompt_version,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    outcome=outcome,
                    langsmith_run_id=self._prepared.assistant_message_id,
                    created_at=created_at,
                )
        except IntegrityError:
            return

    async def _stop(self, task: asyncio.Task[None] | None) -> None:
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await self._finish()

    async def _existing_user_message(self) -> MessageRecord | None:
        found: MessageRecord | None = None
        async with open_session(self._service._database_url) as session, UnitOfWork(session):
            found = await ConversationRepository(session).find_user_message(
                self._prepared.conversation_id,
                self._prepared.client_message_id,
            )
        return found
