"""Conversas, mensagens, feedback e chaves de convidado. Seção 8.1 do SDD."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.grounding import Citation
from app.models.conversation import Conversation
from app.models.feedback import Feedback
from app.models.guest_key import GuestKey
from app.models.message import Message


class DuplicateClientMessage(Exception):
    def __init__(self, message_id: UUID) -> None:
        super().__init__("duplicate client message")
        self.message_id = message_id


@dataclass(frozen=True, slots=True)
class GuestKeyRecord:
    id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ConversationRecord:
    id: UUID
    user_id: UUID | None
    guest_key_id: UUID | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class MessageRecord:
    id: UUID
    conversation_id: UUID
    client_message_id: UUID | None
    role: str
    content: str
    citations: tuple[Citation, ...]
    outcome: str | None
    langsmith_run_id: UUID | None
    created_at: datetime


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert_guest_key(self, token_hash: str, created_at: datetime) -> GuestKeyRecord:
        row = GuestKey(token_hash=token_hash, created_at=created_at)
        self._session.add(row)
        await self._session.flush()
        return _guest(row)

    async def get_guest_key_by_hash(self, token_hash: str) -> GuestKeyRecord | None:
        row = await self._session.scalar(select(GuestKey).where(GuestKey.token_hash == token_hash))
        if row is None:
            return None
        return _guest(row)

    async def allocate_conversation_created_at(self, now: datetime) -> datetime:
        latest = await self._session.scalar(select(func.max(Conversation.created_at)))
        if not isinstance(latest, datetime) or latest < now:
            return now
        return latest + timedelta(microseconds=1)

    async def insert_conversation(
        self,
        *,
        user_id: UUID | None,
        guest_key_id: UUID | None,
        created_at: datetime,
    ) -> ConversationRecord:
        row = Conversation(
            user_id=user_id,
            guest_key_id=guest_key_id,
            created_at=created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _conversation(row)

    async def list_for_user(self, user_id: UUID) -> list[ConversationRecord]:
        rows = await self._session.scalars(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.created_at.desc(), Conversation.id.desc())
        )
        return [_conversation(row) for row in rows]

    async def get_conversation(self, conversation_id: UUID) -> ConversationRecord | None:
        row = await self._session.get(Conversation, conversation_id)
        if row is None:
            return None
        return _conversation(row)

    async def find_user_message(
        self,
        conversation_id: UUID,
        client_message_id: UUID,
    ) -> MessageRecord | None:
        row = await self._session.scalar(
            select(Message).where(
                Message.conversation_id == conversation_id,
                Message.client_message_id == client_message_id,
                Message.role == "user",
            )
        )
        if row is None:
            return None
        return _message(row)

    async def list_messages(self, conversation_id: UUID) -> list[MessageRecord]:
        rows = await self._session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
        return [_message(row) for row in rows]

    async def get_message(self, message_id: UUID) -> MessageRecord | None:
        row = await self._session.get(Message, message_id)
        if row is None:
            return None
        return _message(row)

    async def allocate_created_at(self, conversation_id: UUID, now: datetime) -> datetime:
        latest = await self._session.scalar(
            select(func.max(Message.created_at)).where(Message.conversation_id == conversation_id)
        )
        if not isinstance(latest, datetime) or latest < now:
            return now
        return latest + timedelta(microseconds=1)

    async def insert_message(
        self,
        *,
        message_id: UUID,
        conversation_id: UUID,
        client_message_id: UUID | None,
        role: str,
        content: str,
        citations: Sequence[Citation],
        model: str | None,
        prompt_version: str | None,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int | None,
        outcome: str | None,
        langsmith_run_id: UUID | None,
        created_at: datetime,
    ) -> None:
        self._session.add(
            Message(
                id=message_id,
                conversation_id=conversation_id,
                client_message_id=client_message_id,
                role=role,
                content=content,
                citations=_citations_to_stored(citations),
                model=model,
                prompt_version=prompt_version,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                outcome=outcome,
                langsmith_run_id=langsmith_run_id,
                created_at=created_at,
            )
        )
        await self._session.flush()

    async def insert_feedback(self, message_id: UUID, rating: int, created_at: datetime) -> None:
        self._session.add(Feedback(message_id=message_id, rating=rating, created_at=created_at))
        await self._session.flush()


def _guest(row: GuestKey) -> GuestKeyRecord:
    return GuestKeyRecord(id=row.id, created_at=row.created_at)


def _conversation(row: Conversation) -> ConversationRecord:
    return ConversationRecord(
        id=row.id,
        user_id=row.user_id,
        guest_key_id=row.guest_key_id,
        created_at=row.created_at,
    )


def _message(row: Message) -> MessageRecord:
    return MessageRecord(
        id=row.id,
        conversation_id=row.conversation_id,
        client_message_id=row.client_message_id,
        role=row.role,
        content=row.content,
        citations=_citations_from_stored(row.citations),
        outcome=row.outcome,
        langsmith_run_id=row.langsmith_run_id,
        created_at=row.created_at,
    )


def _citations_to_stored(citations: Sequence[Citation]) -> list[dict[str, object]]:
    return [
        {
            "index": citation.index,
            "document_title": citation.document_title,
            "heading": citation.heading,
            "chunk_id": str(citation.chunk_id),
        }
        for citation in citations
    ]


def _citations_from_stored(value: object) -> tuple[Citation, ...]:
    if not isinstance(value, list):
        return ()
    found: list[Citation] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        heading = item.get("heading")
        chunk_id = item.get("chunk_id")
        index = item.get("index")
        title = item.get("document_title")
        if (
            not isinstance(index, int)
            or not isinstance(title, str)
            or not isinstance(chunk_id, str)
        ):
            continue
        found.append(
            Citation(
                index=index,
                document_title=title,
                heading=heading if isinstance(heading, str) else None,
                chunk_id=UUID(chunk_id),
            )
        )
    return tuple(found)
