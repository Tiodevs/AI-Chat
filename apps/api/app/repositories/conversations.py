"""Conversas, mensagens, feedback e chaves de convidado. Seção 8.1 do SDD.

Camada de repositório (seção 6.2 do SDD). Lê e grava `guest_keys`, `conversations`, `messages`
e `feedback`. O `ConversationService` usa quase tudo: cria conversas, grava a pergunta e a
resposta em duas transações curtas (seção 6.4) e grava o feedback. O `RegistrationService`
anexa as conversas de convidado ao novo membro, e o `AccountService` lê as conversas para a
exportação. Os métodos devolvem cópias imutáveis (`ConversationRecord`, `MessageRecord`),
desligadas da sessão, e não as entidades do SQLAlchemy. Seções 7.1 e 12 do SDD.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.grounding import Citation
from app.models.conversation import Conversation
from app.models.feedback import Feedback
from app.models.guest_key import GuestKey
from app.models.message import Message


class DuplicateClientMessage(Exception):
    """A pergunta com este `client_message_id` já está gravada na conversa (seção 7.1).

    O `ConversationService` levanta este erro quando o INSERT da pergunta viola a restrição
    única `(conversation_id, client_message_id)`. `message_id` é o id da pergunta já gravada,
    que volta no 409.
    """

    def __init__(self, message_id: UUID) -> None:
        """Guarda o id da pergunta que já estava gravada."""
        super().__init__("duplicate client message")
        self.message_id = message_id


@dataclass(frozen=True, slots=True)
class GuestKeyRecord:
    """Uma chave de convidado, sem o hash do segredo."""

    id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ConversationRecord:
    """Uma conversa e os donos dela, membro, convidado ou os dois."""

    id: UUID
    user_id: UUID | None
    guest_key_id: UUID | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class MessageRecord:
    """O que o serviço precisa de uma mensagem.

    Ficam de fora modelo, versão do prompt, tokens, latência e `request_id`, que só o
    inspetor do admin lê, pelo `InsightsRepository`.
    """

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
    """Consultas de conversas, mensagens, feedback e chaves de convidado."""

    def __init__(self, session: AsyncSession) -> None:
        """Usa a sessão aberta pelo serviço, sem abrir transação própria."""
        self._session = session

    async def insert_guest_key(self, token_hash: str, created_at: datetime) -> GuestKeyRecord:
        """Grava uma chave de convidado nova. O `flush()` traz de volta o id gerado no banco."""
        row = GuestKey(token_hash=token_hash, created_at=created_at)
        self._session.add(row)
        await self._session.flush()
        return _guest(row)

    async def get_guest_key_by_hash(self, token_hash: str) -> GuestKeyRecord | None:
        """Procura a chave pelo SHA-256 do cookie `atrium_guest`, com o índice único do hash."""
        row = await self._session.scalar(select(GuestKey).where(GuestKey.token_hash == token_hash))
        if row is None:
            return None
        return _guest(row)

    async def allocate_conversation_created_at(self, now: datetime) -> datetime:
        """Horário de criação de uma conversa nova, depois da conversa mais nova do banco.

        Devolve `now`, ou um microssegundo depois do maior `created_at` quando `now` não passa
        dele, como com o relógio parado dos testes (`FrozenClock`). O `max` olha todas as
        conversas, sem filtro e sem índice em `created_at`, então percorre a tabela. Não há
        trava: duas criações simultâneas podem receber o mesmo valor, e a listagem desempata
        por `id`.
        """
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
        """Grava uma conversa. A restrição `conversations_owner` exige ao menos um dono."""
        row = Conversation(
            user_id=user_id,
            guest_key_id=guest_key_id,
            created_at=created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _conversation(row)

    async def list_for_user(self, user_id: UUID) -> list[ConversationRecord]:
        """Conversas do membro, da mais recente para a mais antiga (seção 12).

        Usa o B-tree `conversations_user_id_idx`. O `id` desempata conversas do mesmo instante.
        """
        rows = await self._session.scalars(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.created_at.desc(), Conversation.id.desc())
        )
        return [_conversation(row) for row in rows]

    async def attach_to_user(self, *, guest_key_id: UUID, user_id: UUID) -> None:
        """A conversa de convidado passa a ser do membro. Seção 7.2.

        Só muda conversas da chave que ainda não têm membro. O `guest_key_id` continua
        preenchido, e por isso a chave de convidado ainda abre a conversa; a Etapa 15.1 corrige.
        """
        await self._session.execute(
            update(Conversation)
            .where(
                Conversation.guest_key_id == guest_key_id,
                Conversation.user_id.is_(None),
            )
            .values(user_id=user_id)
        )

    async def get_conversation(self, conversation_id: UUID) -> ConversationRecord | None:
        """Busca a conversa pela chave primária.

        `AsyncSession.get` olha primeiro o mapa de identidade da sessão e só consulta o banco
        se a entidade ainda não foi carregada.
        """
        row = await self._session.get(Conversation, conversation_id)
        if row is None:
            return None
        return _conversation(row)

    async def find_user_message(
        self,
        conversation_id: UUID,
        client_message_id: UUID,
    ) -> MessageRecord | None:
        """Pergunta já gravada com este `client_message_id`, ou `None` (seção 7.1).

        A busca casa com a restrição única da tabela e usa o índice dela. O serviço chama antes
        de consumir o limite de taxa e depois de um INSERT recusado, para responder 409 com o id.
        """
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
        """Mensagens da conversa em ordem cronológica, com o `id` como desempate.

        Serve à leitura da conversa, à exportação e ao histórico enviado ao modelo, que é lido
        do banco a cada pergunta (seção 7.1).
        """
        rows = await self._session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
        return [_message(row) for row in rows]

    async def get_message(self, message_id: UUID) -> MessageRecord | None:
        """Busca a mensagem pela chave primária, como na gravação do feedback."""
        row = await self._session.get(Message, message_id)
        if row is None:
            return None
        return _message(row)

    async def allocate_created_at(self, conversation_id: UUID, now: datetime) -> datetime:
        """Horário de uma mensagem nova, depois da mensagem mais nova da conversa.

        Devolve `now`, ou um microssegundo depois do maior `created_at` da conversa. Assim a
        resposta fica sempre depois da pergunta na ordem por data, mesmo com o relógio parado.
        O `max` filtra por `conversation_id`, que tem índice.
        """
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
        request_id: str | None = None,
    ) -> None:
        """Grava uma pergunta ou uma resposta.

        O `flush()` envia o INSERT na hora. Um `client_message_id` repetido na conversa viola
        a restrição única e levanta `IntegrityError` aqui, e o serviço o transforma em
        `DuplicateClientMessage`.
        """
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
                request_id=request_id,
                created_at=created_at,
            )
        )
        await self._session.flush()

    async def first_questions(self, conversation_ids: Sequence[UUID]) -> dict[UUID, str]:
        """Primeira pergunta gravada de cada conversa. Seção 15.5, aba Conversas.

        Uma consulta só para a lista inteira: lê todas as perguntas das conversas, da mais nova
        para a mais antiga, e monta um dicionário. Conversa sem pergunta fica fora do resultado.
        """
        if not conversation_ids:
            return {}
        rows = await self._session.execute(
            select(Message.conversation_id, Message.content)
            .where(Message.conversation_id.in_(conversation_ids), Message.role == "user")
            .order_by(Message.created_at.desc(), Message.id.desc())
        )
        # A ordem decrescente deixa a primeira pergunta como última atribuição.
        return {conversation_id: content for conversation_id, content in rows}

    async def feedback_ratings(self, message_ids: Sequence[UUID]) -> dict[UUID, int]:
        """Nota de cada mensagem que tem feedback, para a exportação do titular."""
        if not message_ids:
            return {}
        rows = await self._session.execute(
            select(Feedback.message_id, Feedback.rating).where(Feedback.message_id.in_(message_ids))
        )
        return {message_id: rating for message_id, rating in rows}

    async def insert_feedback(self, message_id: UUID, rating: int, created_at: datetime) -> None:
        """Grava a nota de uma resposta.

        A chave primária de `feedback` é a mensagem. Uma segunda nota levanta `IntegrityError`
        no `flush()`, e o serviço responde 409.
        """
        self._session.add(Feedback(message_id=message_id, rating=rating, created_at=created_at))
        await self._session.flush()


def _guest(row: GuestKey) -> GuestKeyRecord:
    """Copia a entidade num registro imutável."""
    return GuestKeyRecord(id=row.id, created_at=row.created_at)


def _conversation(row: Conversation) -> ConversationRecord:
    """Copia a entidade num registro imutável."""
    return ConversationRecord(
        id=row.id,
        user_id=row.user_id,
        guest_key_id=row.guest_key_id,
        created_at=row.created_at,
    )


def _message(row: Message) -> MessageRecord:
    """Copia a entidade num registro imutável e lê as citações do JSONB."""
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
    """Transforma as citações na lista JSON de `messages.citations`.

    O `chunk_id` vira texto, porque JSON não tem tipo UUID.
    """
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
    """Lê `messages.citations` de volta para `Citation`.

    O JSONB não tem schema no banco, então a leitura é defensiva: um item fora do formato
    esperado é ignorado, em vez de quebrar a leitura da conversa.
    """
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
