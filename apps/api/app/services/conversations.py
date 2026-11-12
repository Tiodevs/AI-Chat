"""Conversas por HTTP: duas transações curtas e o fluxo SSE. Seções 6.4 e 7.1.

Camada de serviço. `controllers/conversations.py` chama `ConversationService`, montado por
pedido em `core/container.py:get_conversation_service` com o `QaWorkflow` do `AiRuntime`
(um por processo, com o circuit breaker do Gemini), o orçamento `PostgresTokenBudget` e o
`FeedbackSink` do LangSmith. Usa `ConversationRepository`, `AuthSessionRepository` e
`RateLimitRepository`, as regras de `domain/questions.py` e `domain/auth.py`, e os eventos
de `conversation_events.py`. Cobre criar, listar e ler conversas, perguntar, avaliar uma
resposta e o limite do diagnóstico do fluxo.

A pergunta tem duas fases:

1. `prepare_ask` roda antes de a resposta HTTP começar. Confere dono, reenvio, limite de
   taxa e orçamento, e lê o histórico. Um erro aqui vira o envelope JSON da seção 12.
2. `stream` devolve o gerador assíncrono que o controlador transmite como
   `text/event-stream`. O `QaWorkflow` roda numa tarefa à parte e manda os tokens por uma
   fila. A transação 1 grava a mensagem do visitante assim que o workflow classifica a
   pergunta, ou no fim, se a classificação não aconteceu. A transação 2 grava a resposta
   no fim. Nenhuma das duas fica aberta durante uma chamada ao modelo.

As "duas transações" da seção 6.4 são as que gravam mensagens. Em volta delas há outras,
também curtas: leituras da sessão e da chave de convidado, a de `prepare_ask`, que grava o
contador do limite, e as do orçamento, que lê e soma `token_usage_days`.

Divergências com o SDD, que a Etapa 13.4 resolve: a seção 6.4 diz que a desconexão cancela
e grava `cancelled`, e a seção 7.1 diz que o pedido continua até o fim; o código cancela.
O `visitor_type` vai sempre `None` ao workflow, embora a seção 7.1 o use com a
personalização.
"""

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

from app import __version__
from app.adapters.noop_feedback import NoopFeedbackSink
from app.adapters.session_secret import new_session_secret
from app.core.metrics import FEEDBACK
from app.core.sse import (
    DISCONNECTED,
    KEEPALIVE,
    KEEPALIVE_COMMENT,
    SSE_KEEPALIVE_SECONDS,
    next_stream_item,
)
from app.core.trace import current_trace_id
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
    HandoffActive,
    NotFound,
    RateLimited,
    Unauthenticated,
    ValidationFailed,
)
from app.domain.feedback import USER_HELPFUL, user_helpful_score
from app.domain.grounding import Citation
from app.domain.history import ai_messages
from app.domain.outcomes import Outcome
from app.domain.pseudonym import subject_pseudonym
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
from app.domain.trace_policy import TraceMetadata
from app.ports.budget import TokenBudget
from app.ports.chat import UsageTally
from app.ports.clock import Clock
from app.ports.feedback import FeedbackSink
from app.prompts.auth import UNAUTHENTICATED, VALIDATION
from app.prompts.conversations import (
    CONVERSATION_NOT_FOUND,
    DIAGNOSTICS_RATE_LIMITED,
    DUPLICATE_FEEDBACK,
    DUPLICATE_MESSAGE,
    FEEDBACK_NOT_ASSISTANT,
    MESSAGE_NOT_FOUND,
    RATE_LIMITED,
    STREAM_FAILED,
)
from app.prompts.handoff import ACTIVE_HERE
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.conversations import (
    ConversationRecord,
    ConversationRepository,
    DuplicateClientMessage,
    MessageRecord,
)
from app.repositories.handoffs import HandoffRecord, HandoffRepository
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

# Sentinela que a tarefa do workflow põe na fila ao terminar, com sucesso ou não, para o
# laço de leitura do fluxo parar.
_STOP = object()


@dataclass(frozen=True, slots=True)
class PreparedQuestion:
    """O que `prepare_ask` resolveu e `stream` usa, já sem cookie nem IP.

    `history` vem do banco, lido antes da pergunta nova: uma pergunta de saúde anterior
    aparece só como o marcador (seção 11.4). A janela da seção 7.1 é aplicada pelo
    workflow. `budget_exceeded` fica decidido antes do fluxo. `assistant_message_id` é o id
    que a resposta terá: vai no evento `meta`, vira a chave primária da mensagem e o id do
    run raiz no LangSmith (seção 18.4). `subject_id` é o id do membro ou da chave de
    convidado, que o rastro recebe como pseudônimo.
    """

    conversation_id: UUID
    text: str
    client_message_id: UUID
    history: tuple[ConversationTurn, ...]
    budget_exceeded: bool
    request_id: str
    assistant_message_id: UUID
    subject_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class FeedbackNotice:
    """O feedback que a tarefa de fundo manda ao LangSmith depois da resposta HTTP.

    `run_id` é o run da resposta avaliada. `score` é 1.0 para útil e 0.0 para não útil.
    """

    run_id: UUID
    score: float


async def send_user_feedback(sink: FeedbackSink, notice: FeedbackNotice) -> None:
    """Falha no LangSmith fica no log. O visitante já recebeu a resposta.

    Grava a nota `user_helpful` no run (seção 18.4). Roda numa tarefa de fundo do FastAPI,
    fora de transação. O log `feedback.langsmith_failed` leva só o tipo da exceção.
    """
    try:
        await sink.record(notice.run_id, USER_HELPFUL, notice.score)
    except Exception as exc:
        structlog.get_logger("atrium").warning(
            "feedback.langsmith_failed",
            error_type=type(exc).__name__,
        )


@dataclass(frozen=True, slots=True)
class _Actor:
    """Quem pede: o membro da sessão, a chave de convidado do cookie, ou os dois."""

    user_id: UUID | None
    guest_key_id: UUID | None


class ConversationService:
    """Casos de uso das conversas e da pergunta com fluxo (seções 7.1 e 12).

    Dependências: `hmac_key` é a `RATE_LIMIT_HMAC_KEY` dos baldes, `app_env` decide o
    `Secure` do cookie de convidado, `workflow` é o `QaWorkflow` compartilhado pelo
    processo, `pseudonym_key` é a `PSEUDONYM_KEY` do pseudônimo nos rastros e
    `feedback_sink` recebe o feedback; sem ele, nada sai do processo.
    """

    def __init__(
        self,
        *,
        database_url: str,
        clock: Clock,
        hmac_key: str,
        app_env: str,
        workflow: QaWorkflow,
        budget: TokenBudget,
        pseudonym_key: str = "",
        feedback_sink: FeedbackSink | None = None,
    ) -> None:
        self._database_url = database_url
        self._clock = clock
        self._hmac_key = hmac_key
        self._app_env = app_env
        self._workflow = workflow
        self._budget = budget
        self._pseudonym_key = pseudonym_key
        self._feedback = feedback_sink or NoopFeedbackSink()

    async def create(
        self,
        *,
        session_secret: str | None,
        guest_secret: str | None,
    ) -> tuple[ConversationRecord, SessionCookie | None]:
        """Cria uma conversa para a sessão ou, sem sessão, para a chave de convidado.

        Com o cookie de sessão, a conversa é do membro; uma sessão inválida responde 401,
        sem cair para convidado. Sem ele, usa a chave de convidado do cookie ou cria uma, e
        então devolve o cookie `atrium_guest` para o controlador definir. Leituras curtas
        resolvem os cookies, e uma transação grava a conversa (outra, antes, grava a chave
        nova). O `created_at` sai depois do da conversa mais nova, para a lista do membro
        manter a ordem mesmo quando o relógio repete o instante.
        """
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

    async def list_for_member(
        self, session_secret: str | None
    ) -> list[tuple[ConversationRecord, str | None]]:
        """Conversas do membro, da mais recente à mais antiga, com a primeira pergunta.

        Exige sessão válida (401). A primeira pergunta pode ser o marcador de saúde. Uma
        transação curta de leitura, além da leitura da sessão.
        """
        if not session_secret:
            raise Unauthenticated(UNAUTHENTICATED)
        user_id = await self._lookup_user(session_secret)
        if user_id is None:
            raise Unauthenticated(UNAUTHENTICATED)
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = ConversationRepository(session)
            records = await repository.list_for_user(user_id)
            questions = await repository.first_questions([record.id for record in records])
        return [(record, questions.get(record.id)) for record in records]

    async def get(
        self,
        conversation_id: UUID,
        *,
        session_secret: str | None,
        guest_secret: str | None,
    ) -> tuple[ConversationRecord, list[MessageRecord], list[HandoffRecord]]:
        """A conversa com as mensagens e os atendimentos humanos, só para o dono.

        As mensagens incluem as do atendimento, com `handoff_id` (seção 29.10).

        Erros: 401 sem sessão nem chave de convidado válidas e 404 para id desconhecido ou
        para quem não é o dono, sem revelar que o id existe (Etapa 15.1, seção 29.8). A
        leitura é uma transação curta, e os erros sobem depois que ela fecha.
        """
        actor = await self._actor(session_secret, guest_secret)
        conversation: ConversationRecord | None
        messages: list[MessageRecord]
        handoffs: list[HandoffRecord] = []
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = ConversationRepository(session)
            conversation = await repository.get_conversation(conversation_id)
            messages = []
            if conversation is not None and _owns(actor, conversation):
                messages = await repository.list_messages(conversation_id)
                handoffs = await HandoffRepository(session).list_for_conversation(conversation_id)
        if conversation is None or not _owns(actor, conversation):
            raise NotFound(CONVERSATION_NOT_FOUND)
        return conversation, messages, handoffs

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
        """Tudo o que precisa acontecer antes do primeiro byte do fluxo.

        1. Confere o texto: de 1 a 1.000 caracteres. O schema já confere; a regra se repete
           para quem chama sem HTTP.
        2. Exige a chave HMAC dos baldes.
        3. Resolve quem pede pela sessão e pela chave de convidado (401).
        4. Numa transação: conversa e dono (404 para os dois), atendimento humano ativo (409
           `handoff_active`, seção 29.5), reenvio do mesmo
           `client_message_id` e, se não for reenvio, o balde de perguntas e o histórico.
        5. Fora da transação, levanta o 409 do reenvio, com o `message_id` já gravado, ou o
           429 do limite. O contador incrementado fica confirmado.
        6. Confere o orçamento, numa leitura própria, e sorteia o id da resposta.

        O reenvio não consome o balde nem chama o modelo (seção 7.1). Esta fase não chama o
        modelo.
        """
        # 1.
        if not text or len(text) > MAX_QUESTION_CHARS:
            raise ValidationFailed(VALIDATION)
        # 2.
        self._require_hmac()
        # 3.
        actor = await self._actor(session_secret, guest_secret)
        now = self._clock.now()
        existing_id: UUID | None = None
        history: tuple[ConversationTurn, ...] = ()
        limited = False
        retry_after = 0
        # 4.
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = ConversationRepository(session)
            conversation = await repository.get_conversation(conversation_id)
            if conversation is None or not _owns(actor, conversation):
                raise NotFound(CONVERSATION_NOT_FOUND)
            # Com a conversa na equipe, a pergunta não grava nada nem chama o modelo (FR-21).
            active = await HandoffRepository(session).active_for_conversation(conversation_id)
            if active is not None:
                raise HandoffActive(
                    ACTIVE_HERE, handoff_id=active.id, conversation_id=conversation_id
                )
            # A chave de idempotência é o par (conversa, `client_message_id`).
            existing = await repository.find_user_message(conversation_id, client_message_id)
            if existing is not None:
                existing_id = existing.id
            else:
                decision = await self._consume_question_rate(session, actor, client_ip, now)
                limited = decision.limited
                retry_after = decision.retry_after_seconds
                history = _turns(await repository.list_messages(conversation_id))
        # 5.
        if existing_id is not None:
            raise DuplicateMessage(DUPLICATE_MESSAGE, message_id=existing_id)
        if limited:
            raise RateLimited(RATE_LIMITED, retry_after_seconds=retry_after)
        # 6.
        return PreparedQuestion(
            conversation_id=conversation_id,
            text=text,
            client_message_id=client_message_id,
            history=history,
            budget_exceeded=await self._budget.exceeded(),
            request_id=request_id,
            assistant_message_id=uuid4(),
            subject_id=actor.user_id or actor.guest_key_id,
        )

    def stream(
        self,
        prepared: PreparedQuestion,
        disconnected: asyncio.Event,
    ) -> AsyncIterator[AskEvent]:
        """Os eventos da resposta, na ordem da seção 7.1.

        Um gerador assíncrono entrega cada evento assim que ele existe, então o controlador
        transmite os tokens enquanto o modelo ainda escreve. `disconnected` é ligado pelo
        controlador quando o navegador fecha a conexão. Os detalhes estão em `_AskStream`.
        """
        return _AskStream(self, prepared, disconnected).events()

    async def submit_feedback(
        self,
        message_id: UUID,
        rating: int,
        *,
        session_secret: str | None,
        guest_secret: str | None,
    ) -> FeedbackNotice | None:
        """Grava a nota do visitante para uma resposta do assistente, uma vez só.

        Numa transação: mensagem e dono da conversa (404), papel `assistant` (422) e a
        nota. A chave primária de `feedback` é o id da mensagem, então a segunda nota
        levanta `IntegrityError` e responde 409. Depois da transação, conta
        `atrium_feedback{rating}`. Devolve o aviso que o controlador agenda para o LangSmith
        depois da resposta, ou `None` se a mensagem não tem run.
        """
        actor = await self._actor(session_secret, guest_secret)
        run_id: UUID | None = None
        try:
            async with open_session(self._database_url) as session, UnitOfWork(session):
                repository = ConversationRepository(session)
                message = await repository.get_message(message_id)
                if message is None:
                    raise NotFound(MESSAGE_NOT_FOUND)
                conversation = await repository.get_conversation(message.conversation_id)
                if conversation is None or not _owns(actor, conversation):
                    raise NotFound(MESSAGE_NOT_FOUND)
                if message.role != "assistant":
                    raise ValidationFailed(FEEDBACK_NOT_ASSISTANT)
                await repository.insert_feedback(message_id, rating, self._clock.now())
                run_id = message.langsmith_run_id
        except IntegrityError:
            raise Conflict(DUPLICATE_FEEDBACK) from None
        FEEDBACK.labels(rating="helpful" if rating == 1 else "not_helpful").inc()
        if run_id is None:
            return None
        return FeedbackNotice(run_id=run_id, score=user_helpful_score(rating))

    async def deliver_feedback(self, notice: FeedbackNotice) -> None:
        """A tarefa de fundo do feedback: manda a nota ao `FeedbackSink`, pela rede."""
        await send_user_feedback(self._feedback, notice)

    async def prepare_diagnostics(self, client_ip: str) -> None:
        """Conta o pedido no balde de 60 por hora por IP do `/v1/diagnostics/stream`.

        Roda antes de o fluxo de diagnóstico começar (seções 10.4 e 12). A transação
        confirma o contador, e o 429 sobe depois dela.
        """
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
        """Resolve quem pede. Sem membro nem convidado válidos, `Unauthenticated` (401).

        Um cookie de sessão que não resolve responde 401 mesmo com a chave de convidado
        válida: uma sessão revogada não vira convidado em silêncio.
        """
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
        """Id do membro da sessão ativa, achada pelo SHA-256 do segredo. Leitura própria."""
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            sessions = AuthSessionRepository(session)
            found = await sessions.get_active(hash_session_secret(secret), now)
        if found is None:
            return None
        return found.user_id

    async def _lookup_guest(self, secret: str) -> UUID | None:
        """Id da chave de convidado do cookie, pelo SHA-256 do segredo. Leitura própria.

        A chave não vence aqui: o cookie dura 30 dias e o `retention-job` apaga a chave
        depois desse prazo (seção 11.6).
        """
        async with open_session(self._database_url) as session, UnitOfWork(session):
            found = await ConversationRepository(session).get_guest_key_by_hash(
                hash_session_secret(secret)
            )
        if found is None:
            return None
        return found.id

    async def _ensure_guest(self, secret: str | None) -> tuple[UUID, SessionCookie | None]:
        """Reaproveita a chave de convidado do cookie ou cria uma nova.

        A chave nova tem um segredo de 256 bits que só o cookie guarda; o banco fica com o
        SHA-256 (seção 8.1). Devolve o cookie só quando criou a chave.
        """
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
        """Conta a pergunta nos baldes da seção 10.4, na transação de quem chama.

        Membro: 120 por hora por usuário. Convidado: 30 por hora por chave e 60 por hora por
        IP, os dois contados em toda pergunta, e o maior `retry_after` vale. As chaves são
        HMAC com o sal do dia, nunca o IP cru.
        """
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
        # Defesa: `_actor` já garante um dos dois ids.
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

    def _trace_metadata(self, prepared: PreparedQuestion) -> TraceMetadata:
        """Metadados do rastro do LangSmith (seção 18.4), sem texto nem id cru.

        Levam o ambiente, a versão, a conversa, o pseudônimo do titular e o `trace_id` do
        OpenTelemetry, para navegar entre os dois rastros.
        """
        return TraceMetadata(
            environment=self._app_env,
            app_version=__version__,
            conversation_id=str(prepared.conversation_id),
            subject=self._subject(prepared.subject_id),
            trace_id=current_trace_id(),
        )

    def _subject(self, subject_id: UUID | None) -> str | None:
        """HMAC do id do membro ou da chave de convidado com a `PSEUDONYM_KEY`.

        Sem chave, como em `local` e `test`, o rastro vai sem `subject`. O pseudônimo perde o
        vínculo com a pessoa quando a conta some (seção 11.6).
        """
        if subject_id is None or not self._pseudonym_key:
            return None
        return subject_pseudonym(subject_id, self._pseudonym_key)

    def _require_hmac(self) -> None:
        """Sem `RATE_LIMIT_HMAC_KEY` não há balde: falha como erro de servidor (500).

        É melhor que deixar a pergunta passar sem limite. Em `development` e `production` a
        API nem sobe sem a chave (`core/config.py:require_safeguards`).
        """
        if not self._hmac_key:
            raise RuntimeError("RATE_LIMIT_HMAC_KEY vazio.")


def _owns(actor: _Actor, conversation: ConversationRecord) -> bool:
    """A regra de dono do domínio: o membro pelo `user_id`, o convidado pela chave.

    A chave de convidado só abre a conversa que ainda não tem membro (Etapa 15.1).
    """
    return owns_conversation(
        actor_user_id=actor.user_id,
        actor_guest_key_id=actor.guest_key_id,
        owner_user_id=conversation.user_id,
        owner_guest_key_id=conversation.guest_key_id,
    )


def _turns(rows: Sequence[MessageRecord]) -> tuple[ConversationTurn, ...]:
    """As mensagens gravadas como turnos do histórico, na ordem da conversa.

    O conteúdo vem do banco, então uma pergunta de saúde aparece só como o marcador. Uma
    resposta `cancelled` entra com o conteúdo vazio. As mensagens do atendimento humano saem
    antes, por `ai_messages` (FR-21), e outros papéis são ignorados.
    """
    turns: list[ConversationTurn] = []
    for row in ai_messages(rows):
        if row.role == "user":
            turns.append(ConversationTurn(role="user", content=row.content))
        elif row.role == "assistant":
            turns.append(ConversationTurn(role="assistant", content=row.content))
    return tuple(turns)


class _Sink:
    """A porta `QaEventSink` do workflow, ligada a um `_AskStream`.

    Roda na tarefa do workflow. `classified` dispara a transação 1 com a intenção, antes do
    embedding: assim uma pergunta de orientação médica já é gravada como o marcador
    (seção 7.1). `token` põe cada pedaço na fila e conta quantos saíram.
    """

    def __init__(self, stream: "_AskStream") -> None:
        self._stream = stream

    async def classified(self, intent: str) -> None:
        """Chamado pelo workflow logo depois da classificação."""
        await self._stream.save_user(intent)

    async def token(self, text: str) -> None:
        """Chamado a cada pedaço do rascunho em fluxo."""
        self._stream.tokens_seen += 1
        await self._stream.queue.put(text)


class _AskStream:
    """O estado de uma pergunta em fluxo, do `meta` ao `done`.

    Duas tarefas cooperam. O gerador `events` roda na tarefa da resposta HTTP. O workflow
    roda em outra, criada por `asyncio.create_task` em `_execute`, para o gerador poder
    mandar `: keepalive` e perceber a desconexão enquanto o modelo pensa. A fila leva os
    tokens de uma tarefa à outra.

    Dois locks evitam gravação dupla: `_user_lock` impede duas inserções da mensagem do
    visitante, pelo `_Sink` e pelo `_store` final, e `_lock` faz `_finish` rodar uma vez,
    mesmo chamado pelo caminho normal e pelo `finally`. `usage` é o `UsageTally` que o
    adaptador preenche a cada pedaço do fluxo, então o uso parcial de uma resposta cancelada
    é conhecido. A latência conta a partir da criação deste objeto.
    """

    def __init__(
        self,
        service: ConversationService,
        prepared: PreparedQuestion,
        disconnected: asyncio.Event,
    ) -> None:
        self._service = service
        self._prepared = prepared
        self._disconnected = disconnected
        # Tokens em texto e, no fim, a sentinela `_STOP`.
        self.queue: asyncio.Queue[object] = asyncio.Queue()
        # Quantos tokens já saíram. Decide entre `replace` e um `token` só, no fim.
        self.tokens_seen = 0
        self.usage = UsageTally()
        self._lock = asyncio.Lock()
        self._user_lock = asyncio.Lock()
        self._user_saved = False
        # Outro pedido com o mesmo `client_message_id` gravou a mensagem do visitante.
        self._duplicate = False
        self._stored = False
        self._usage_recorded = False
        self._result: QaResult | None = None
        self._error: BaseException | None = None
        self._started = time.perf_counter()

    async def events(self) -> AsyncIterator[AskEvent]:
        """Produz os eventos SSE de uma pergunta.

        1. Orçamento estourado: grava as duas mensagens, com desfecho `degraded`, antes do
           primeiro evento, e emite `meta`, o texto fixo num `token` e `done`. O modelo não
           é chamado.
        2. Senão, emite `meta` primeiro e põe o workflow para rodar na outra tarefa.
        3. Lê a fila: cada token vira `token`; 15 s sem nada viram `: keepalive`; a
           desconexão encerra o gerador, e o `finally` cancela o workflow e grava
           `cancelled`.
        4. Depois de `_STOP`: um reenvio que perdeu a corrida emite `error` com `conflict` e
           não grava mensagem; uma falha grava `error` e emite `error`; o resto grava a
           resposta (transação 2) e emite `replace` ou o texto fixo, as citações e `done`.

        O `finally` passa por `asyncio.shield`: se a tarefa da resposta for cancelada,
        `_stop` termina mesmo assim, em segundo plano, e o desfecho fica gravado.
        """
        task: asyncio.Task[None] | None = None
        try:
            # 1. A resposta fixa sai inteira; nada fica para o `finally`.
            if self._prepared.budget_exceeded:
                self._result = degraded_result(self._prepared.assistant_message_id)
                await self._finish()
            # 2. `meta` é sempre o primeiro evento (seção 7.1).
            yield MetaEvent(self._prepared.assistant_message_id, self._prepared.request_id)
            if self._prepared.budget_exceeded and self._result is not None:
                yield TokenEvent(self._result.text)
                yield DoneEvent(self._result.outcome.value)
                return
            task = asyncio.create_task(self._execute())
            # 3.
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
            # 4. A tarefa já pôs `_STOP`; aqui só termina de sair.
            if task is not None:
                await task
                task = None
            # As mensagens desta pergunta são do pedido que gravou primeiro.
            if self._duplicate or isinstance(self._error, DuplicateClientMessage):
                self._stored = True
                yield ErrorEvent("conflict", DUPLICATE_MESSAGE)
                return
            # Uma exceção que não é erro da porta, como uma falha de rede do embedding, chega
            # aqui: o desfecho `error` é gravado, mas o workflow não o conta em
            # `atrium_qa_outcomes` (Etapa 13.2).
            if self._error is not None or self._result is None:
                self._result = error_result(self._prepared.assistant_message_id)
                await self._finish()
                yield ErrorEvent("error", STREAM_FAILED)
                return
            # A transação 2 confirma antes do `done`: a consulta de reserva da visão já
            # encontra o desfecho.
            await self._finish()
            result = self._result
            # A fundamentação falhou depois de tokens enviados: a visão troca o balão.
            if self.tokens_seen and result.outcome is Outcome.GROUNDING_FAILED:
                yield ReplaceEvent(result.text, "grounding_failed")
            # Resposta fixa sem rascunho transmitido: o texto inteiro num evento só. Uma
            # falha do provedor depois de tokens enviados não cai em nenhum dos dois casos.
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
        """Roda o `QaWorkflow` na tarefa à parte e guarda o resultado ou o erro.

        Chama o Gemini e o embedding pela rede, sem transação aberta; a transação 1 acontece
        no meio, pelo `_Sink`. Uma falha fica em `_error` e vai para o log
        `question.failed` só com o tipo; o reenvio não é registrado, porque é uma corrida
        esperada. O cancelamento sobe, para a desconexão parar o workflow. O `finally`
        sempre põe `_STOP` na fila.
        """
        try:
            self._result = await self._service._workflow.run(
                self._prepared.text,
                history=self._prepared.history,
                # Seção 7.1: com a personalização, o tipo de visitante entraria na
                # reescrita. A Etapa 13.4 decide se ele entra ou sai do SDD.
                visitor_type=None,
                request_id=self._prepared.request_id,
                run_id=self._prepared.assistant_message_id,
                events=_Sink(self),
                trace_metadata=self._service._trace_metadata(self._prepared),
                usage=self.usage,
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
        """Transação 1: grava a mensagem do visitante, uma vez só.

        O conteúdo vem de `domain/questions.py:stored_user_content`: o marcador
        `[health-related message not stored]` para `medical_advice`, o texto enviado para o
        resto. O `_Sink` chama logo depois da classificação. `_store` chama no fim quando a
        classificação não aconteceu (orçamento estourado, falha na reescrita, desconexão
        antes dela), e aí `intent` é `None` e o texto original é gravado.

        Uma `IntegrityError` com o mesmo `client_message_id` já gravado quer dizer que outro
        pedido ganhou a corrida depois de `prepare_ask`: marca o reenvio e levanta
        `DuplicateClientMessage`. Outra `IntegrityError` sobe como veio.
        """
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
                    # Um instante maior que o da última mensagem mantém a ordem da conversa.
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
                        request_id=self._prepared.request_id,
                    )
            except IntegrityError:
                existing = await self._existing_user_message()
                if existing is None:
                    raise
                self._duplicate = True
                raise DuplicateClientMessage(existing.id) from None
            self._user_saved = True

    async def _finish(self) -> None:
        """Grava a resposta uma vez e põe no orçamento o uso que os adaptadores contaram.

        O uso vem dos `RunContext` do pedido, então uma resposta cancelada, quebrada ou
        repetida também paga os tokens que o modelo já gerou. Seções 6.4 e 7.1 do SDD.

        Roda pelo caminho normal e de novo pelo `_stop` do `finally`; o lock e as marcas
        fazem o trabalho acontecer uma vez. A soma em `token_usage_days` é uma transação
        própria, depois das mensagens.
        """
        async with self._lock:
            await self._store()
            if self._usage_recorded:
                return
            self._usage_recorded = True
        await self._service._budget.record(self.usage.input_tokens, self.usage.output_tokens)

    async def _store(self) -> None:
        """Grava a mensagem do visitante, se falta, e a resposta, uma vez.

        Num reenvio não grava nada: as mensagens são do pedido que ganhou.
        """
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

    async def _save_assistant(self, result: QaResult | None) -> None:
        """Transação 2: grava a resposta com o passo 8 da seção 7.1.

        Desfecho, citações mantidas, modelo, versão do prompt, tokens, latência, o
        `request_id` e o id do run do LangSmith, igual ao id da mensagem. Sem resultado, a
        pergunta foi cancelada: desfecho `cancelled` e conteúdo vazio, porque o rascunho
        parcial é descartado (seção 6.4). Os tokens vêm do `UsageTally`, não do resultado,
        então incluem o uso parcial. Uma `IntegrityError`, como a da conversa apagada no
        meio do fluxo, deixa a resposta sem gravar e não quebra o fim do pedido.
        """
        input_tokens = self.usage.input_tokens
        output_tokens = self.usage.output_tokens
        if result is None:
            outcome = Outcome.CANCELLED.value
            text = ""
            citations: tuple[Citation, ...] = ()
            model = None
            prompt_version = None
        else:
            outcome = result.outcome.value
            text = result.text
            citations = result.citations
            model = result.model
            prompt_version = result.prompt_version
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
                    request_id=self._prepared.request_id,
                )
        except IntegrityError:
            return

    async def _stop(self, task: asyncio.Task[None] | None) -> None:
        """O fim de todo fluxo: cancela o workflow, se ainda roda, e chama `_finish`.

        Na desconexão, a tarefa ainda está viva: o cancelamento a interrompe, e `_finish`
        grava `cancelled` com os tokens já contados.
        """
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await self._finish()

    async def _existing_user_message(self) -> MessageRecord | None:
        """A mensagem que ganhou a corrida, numa leitura própria.

        A transação da inserção que falhou já foi desfeita.
        """
        found: MessageRecord | None = None
        async with open_session(self._service._database_url) as session, UnitOfWork(session):
            found = await ConversationRepository(session).find_user_message(
                self._prepared.conversation_id,
                self._prepared.client_message_id,
            )
        return found
