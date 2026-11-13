"""Processador, enviador e repasse do canal WhatsApp. Seções 30.4 a 30.6 e ADR-017 do SDD.

Camada de serviço. O `lifespan` de `app/main.py` roda `WhatsAppWorker.run` numa tarefa quando
`WHATSAPP_ENABLED` está ligado. Cada volta do laço faz três coisas, nesta ordem:

1. **Processa** a caixa de entrada: pega um evento por vez, sem transação aberta durante a
   chamada ao modelo, e grava o resultado, as mensagens de saída e o fim do evento numa
   transação só. Um evento processado nunca gera duas respostas.
2. **Repassa** os atendimentos do WhatsApp: as mensagens da equipe e cada mudança de status
   viram mensagens de saída, na mesma transação que avança o cursor do repasse.
3. **Envia** a caixa de saída pela porta `MessagingChannel`, com novas tentativas.

O laço acorda pelo aviso do webhook do mesmo processo, pelo aviso do atendimento humano no
`RealtimeBroker`, ou a cada 2 segundos. O texto do atendimento nunca vai ao modelo: a
pergunta à IA só acontece fora de um atendimento ativo, e o histórico sai de `ai_messages`.
"""

import asyncio
import contextlib
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.core.metrics import (
    WHATSAPP_OUTBOUND,
    WHATSAPP_PROCESSING_LAG,
    WHATSAPP_SEND_ERRORS,
)
from app.core.telemetry import traced_span
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.auth import bucket_key, fixed_window_start
from app.domain.errors import (
    DuplicateMessage,
    HandoffActive,
    HandoffBlocked,
    HandoffClosed,
    HandoffNotOffered,
    HandoffUnavailable,
    NotFound,
    RateLimited,
    ValidationFailed,
)
from app.domain.handoff import (
    Availability,
    HandoffStatus,
    NoticeKind,
    handoff_offer,
    queue_position,
)
from app.domain.history import ai_messages
from app.domain.legal import LEGAL_DOCUMENT_VERSION
from app.domain.pseudonym import subject_pseudonym
from app.domain.questions import stored_user_content
from app.domain.trace_policy import TraceMetadata
from app.domain.whatsapp import (
    AI_PREFIX,
    ERROR_WINDOW_CLOSED,
    MAX_SEND_ATTEMPTS,
    QUESTION_CONTACT_LIMIT,
    QUESTION_CONTACT_PURPOSE,
    QUESTION_WINDOW,
    WAKE_INTERVAL_SECONDS,
    Button,
    Channel,
    Command,
    Decision,
    InboundKind,
    InboundStatus,
    MessageType,
    OutboundKind,
    OutboundStatus,
    ai_text,
    can_fallback_to_phone,
    clean_question,
    is_new_conversation,
    is_retryable,
    next_attempt_delay,
    normalize_command,
    recipient_for,
    staff_text,
    to_whatsapp_text,
    within_service_window,
)
from app.ports.budget import TokenBudget
from app.ports.chat import UsageTally
from app.ports.clock import Clock
from app.ports.messaging import MessagingChannel, SendButton, SendError
from app.ports.realtime import RealtimeBroker
from app.prompts import whatsapp as text
from app.repositories.conversations import ConversationRepository, MessageRecord
from app.repositories.handoffs import HandoffRepository
from app.repositories.rate_limits import RateLimitRepository
from app.repositories.whatsapp import ClaimedEvent, ContactRecord, OutboundJob, WhatsAppRepository
from app.services.handoff import HandoffService
from app.services.visitor import Visitor
from app.workflows.qa import ConversationTurn, QaResult, QaWorkflow, degraded_result, error_result

_LOG = structlog.get_logger("atrium")


@dataclass(frozen=True, slots=True)
class _Outgoing:
    """Uma mensagem a gravar na caixa de saída, ainda sem id."""

    kind: OutboundKind
    payload: dict[str, Any]
    message_id: UUID | None = None
    handoff_id: UUID | None = None


class WhatsAppWorker:
    """O laço do canal: processa, repassa e envia (ADR-017)."""

    def __init__(
        self,
        *,
        database_url: str,
        clock: Clock,
        channel: MessagingChannel,
        workflow: QaWorkflow,
        budget: TokenBudget,
        handoffs: HandoffService,
        broker: RealtimeBroker,
        hmac_key: str,
        pseudonym_key: str,
        app_env: str,
        web_origin: str,
    ) -> None:
        self._database_url = database_url
        self._clock = clock
        self._channel = channel
        self._workflow = workflow
        self._budget = budget
        self._handoffs = handoffs
        self._broker = broker
        self._hmac_key = hmac_key
        self._pseudonym_key = pseudonym_key
        self._app_env = app_env
        self._web_origin = web_origin.rstrip("/")
        self._wake = asyncio.Event()

    def wake(self) -> None:
        """Acorda o laço agora. O webhook chama depois de gravar."""
        self._wake.set()

    async def run(self) -> None:
        """O laço do `lifespan`, até ser cancelado. Uma falha vai para o log e o laço segue."""
        queue = self._broker.subscribe()
        try:
            while True:
                try:
                    await self.run_once()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    _LOG.warning("whatsapp.loop_failed", error_type=type(exc).__name__)
                await self._sleep(queue)
        finally:
            self._broker.unsubscribe(queue)

    async def run_once(self) -> None:
        """Uma volta: processa tudo que está pendente, repassa e envia."""
        while await self.process_next():
            pass
        await self.relay_handoffs()
        while await self.send_next():
            pass

    # 1. Caixa de entrada.

    async def process_next(self) -> bool:
        """Pega e processa um evento. Devolve falso quando não há nenhum."""
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            event = await WhatsAppRepository(session).claim_event(now)
        if event is None:
            return False
        try:
            await self._process(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _LOG.warning("whatsapp.event_failed", error_type=type(exc).__name__)
            async with open_session(self._database_url) as session, UnitOfWork(session):
                await WhatsAppRepository(session).retry_event(
                    event.id, event.attempts, self._clock.now()
                )
        return True

    async def _process(self, event: ClaimedEvent) -> None:
        """Despacha pelo tipo: status de entrega, troca de identidade ou mensagem."""
        if event.kind == InboundKind.STATUS:
            await self._apply_status(event)
            return
        if event.kind == InboundKind.SYSTEM:
            await self._change_identity(event)
            return
        await self._handle_message(event)

    async def _apply_status(self, event: ClaimedEvent) -> None:
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = WhatsAppRepository(session)
            if event.wamid and event.delivery_status:
                await repository.apply_status(
                    wamid=event.wamid,
                    status=OutboundStatus(event.delivery_status),
                    error_code=event.error_code,
                    now=now,
                )
            await repository.finish_event(event.id, InboundStatus.DONE, now)
        if event.delivery_status == OutboundStatus.FAILED and event.error_code is not None:
            WHATSAPP_SEND_ERRORS.labels(error_code=str(event.error_code)).inc()

    async def _change_identity(self, event: ClaimedEvent) -> None:
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = WhatsAppRepository(session)
            if event.previous_identity and event.identity:
                await repository.change_identity(
                    previous=event.previous_identity, current=event.identity, phone=event.phone
                )
            await repository.finish_event(event.id, InboundStatus.DONE, now)

    async def _handle_message(self, event: ClaimedEvent) -> None:
        """Uma mensagem recebida, na ordem da seção 30.4, passo 6."""
        if event.identity is None:
            await self._finish(event, InboundStatus.IGNORED)
            return
        now = self._clock.now()
        # Contato e conversa numa transação curta, antes de qualquer chamada de rede.
        async with open_session(self._database_url) as session, UnitOfWork(session):
            contact, _ = await WhatsAppRepository(session).upsert_contact(
                identity=event.identity, phone=event.phone, now=now
            )
            conversation_id = await self._conversation(session, contact, now)
        if event.wamid:
            with contextlib.suppress(SendError):
                await self._channel.mark_read_typing(event.wamid)
        notice = self._notice(contact)
        visitor = Visitor(user_id=None, guest_key_id=contact.guest_key_id)
        message_type = event.message_type or MessageType.OTHER
        with traced_span("whatsapp.process", message_type=message_type) as span:
            decision, outgoing = await self._decide(
                event, contact, conversation_id, visitor, message_type
            )
            span.set(decision=decision.value)
        if decision is Decision.QUESTION:
            # A pergunta grava as mensagens e as saídas na própria transação.
            await self._answer(event, contact, conversation_id, notice)
        else:
            await self._commit_outgoing(event, contact, conversation_id, notice + outgoing)
        WHATSAPP_PROCESSING_LAG.observe(
            max(0.0, (self._clock.now() - event.wa_timestamp).total_seconds())
        )
        _LOG.info("whatsapp.event_processed", decision=decision.value, message_type=message_type)

    async def _decide(
        self,
        event: ClaimedEvent,
        contact: ContactRecord,
        conversation_id: UUID,
        visitor: Visitor,
        message_type: str,
    ) -> tuple[Decision, list[_Outgoing]]:
        """Escolhe o caminho e devolve as mensagens fixas. A pergunta volta sem mensagens."""
        if message_type == MessageType.MEDIA or message_type == MessageType.OTHER:
            return Decision.MEDIA, [_text(text.MEDIA)]
        if message_type == MessageType.BUTTON:
            return Decision.BUTTON, await self._button(
                event.button_id, contact, conversation_id, visitor
            )
        body = event.body or ""
        command = normalize_command(body)
        if command is Command.DELETE_DATA:
            return Decision.COMMAND, [
                _buttons(text.DELETE_CONFIRM, [Button.DELETE_YES, Button.DELETE_NO])
            ]
        if command is Command.END:
            return Decision.COMMAND, await self._end(conversation_id, visitor)
        if await self._active_handoff(conversation_id) is not None:
            return Decision.HANDOFF, await self._to_handoff(event, body, conversation_id, visitor)
        if clean_question(body) is None:
            return Decision.IGNORED, [_text(text.EMPTY)]
        limited, first_over = await self._question_rate(contact)
        if limited:
            return Decision.RATE_LIMITED, [_text(text.RATE_LIMITED)] if first_over else []
        return Decision.QUESTION, []

    async def _button(
        self,
        button_id: str | None,
        contact: ContactRecord,
        conversation_id: UUID,
        visitor: Visitor,
    ) -> list[_Outgoing]:
        """A ação de cada botão (seções 30.5 e 30.9.6)."""
        if button_id == Button.OFFER_YES:
            return [_buttons(text.CONFIRM, [Button.CONFIRM_YES, Button.CONFIRM_NO])]
        if button_id in (Button.OFFER_NO, Button.CONFIRM_NO):
            return [_text(text.OFFER_DECLINED)]
        if button_id == Button.CONFIRM_YES:
            return await self._request_handoff(contact, conversation_id, visitor)
        if button_id == Button.DELETE_YES:
            await self._delete(contact)
            return []
        if button_id == Button.DELETE_NO:
            return [_text(text.DELETE_CANCELLED)]
        return [_text(text.UNKNOWN_BUTTON)]

    async def _request_handoff(
        self, contact: ContactRecord, conversation_id: UUID, visitor: Visitor
    ) -> list[_Outgoing]:
        """Pede o atendimento pelo mesmo caminho da web (seção 29.5, passo 1).

        Deu certo: o repasse anuncia a posição na fila. Não deu: o texto do motivo.
        """
        async with open_session(self._database_url) as session, UnitOfWork(session):
            last = await HandoffRepository(session).last_answer(conversation_id)
        if last is None:
            return [_text(text.NOT_OFFERED)]
        try:
            await self._handoffs.request(
                conversation_id,
                trigger_message_id=last.message_id,
                session_secret=None,
                guest_secret=None,
                client_ip=f"whatsapp:{contact.id}",
                visitor=visitor,
            )
        except HandoffBlocked:
            return [_text(text.BLOCKED)]
        except HandoffNotOffered:
            return [_text(text.NOT_OFFERED)]
        except HandoffUnavailable as exc:
            busy = getattr(exc, "availability", None) == Availability.BUSY
            return [_text(text.BUSY if busy else text.CLOSED_AVAILABILITY)]
        except HandoffActive:
            return [_text(text.ASSIGNED)]
        except RateLimited:
            return [_text(text.RATE_LIMITED)]
        return []

    async def _end(self, conversation_id: UUID, visitor: Visitor) -> list[_Outgoing]:
        """ENCERRAR: sai da fila ou encerra o atendimento. O repasse anuncia o fim."""
        if await self._active_handoff(conversation_id) is None:
            return [_text(text.NO_HANDOFF)]
        with contextlib.suppress(NotFound):
            await self._handoffs.end(
                conversation_id, session_secret=None, guest_secret=None, visitor=visitor
            )
        return []

    async def _to_handoff(
        self, event: ClaimedEvent, body: str, conversation_id: UUID, visitor: Visitor
    ) -> list[_Outgoing]:
        """Com atendimento ativo, a mensagem vai para a equipe, sem identificadores (29.9.7)."""
        try:
            await self._handoffs.send(
                conversation_id,
                text=body,
                client_message_id=_client_message_id(event),
                session_secret=None,
                guest_secret=None,
                visitor=visitor,
            )
        except RateLimited:
            return [_text(text.RATE_LIMITED)]
        except (ValidationFailed, HandoffClosed, NotFound):
            return [_text(text.EMPTY)]
        except DuplicateMessage:
            # O mesmo `wamid` já está gravado no atendimento: nada a fazer.
            return []
        # Sem fluxo SSE no WhatsApp, a presença do visitante é a última mensagem (30.5).
        async with open_session(self._database_url) as session, UnitOfWork(session):
            handoffs = HandoffRepository(session)
            active = await handoffs.active_for_conversation(conversation_id)
            if active is not None:
                await handoffs.touch_visitor(active.id, self._clock.now())
        return []

    async def _delete(self, contact: ContactRecord) -> None:
        """APAGAR DADOS confirmado: remove tudo do contato e avisa o console (30.9.6).

        A resposta final sai direto pela porta, depois do commit, porque a caixa de saída do
        contato some com ele.
        """
        notices: list[Any] = []
        async with open_session(self._database_url) as session, UnitOfWork(session):
            handoffs = HandoffRepository(session)
            repository = WhatsAppRepository(session)
            conversation_ids = await repository.conversation_ids(contact.guest_key_id)
            for conversation_id in conversation_ids:
                active = await handoffs.active_for_conversation(conversation_id)
                if active is not None:
                    await handoffs.notify(active.id, active.last_seq, NoticeKind.REMOVED)
            notices = list(handoffs.notices)
            await repository.delete_contact(contact.id)
        await self._broker.committed(notices)
        with contextlib.suppress(SendError):
            await self._channel.send_text(
                recipient_for(contact.identity, None), ai_text(text.DELETE_DONE)
            )
        _LOG.info("whatsapp.contact_deleted")

    async def _answer(
        self,
        event: ClaimedEvent,
        contact: ContactRecord,
        conversation_id: UUID,
        notice: list[_Outgoing],
    ) -> None:
        """A pergunta pelo pipeline da seção 7.1, sem fluxo em tempo real.

        1. Lê o histórico da conversa com a IA (sem mensagens do atendimento, FR-21).
        2. Com o orçamento estourado, responde `degraded` sem chamar o modelo.
        3. Roda o `QaWorkflow` sem transação aberta.
        4. Numa transação: a pergunta (o marcador de saúde no lugar do texto médico), a
           resposta, a mensagem de saída, a oferta do atendimento quando cabe e o fim do evento.
        5. Soma no orçamento os tokens que os adaptadores contaram.
        """
        question = clean_question(event.body or "") or ""
        assistant_id = uuid4()
        request_id = f"whatsapp-{assistant_id}"
        # 1.
        async with open_session(self._database_url) as session, UnitOfWork(session):
            history = _turns(await ConversationRepository(session).list_messages(conversation_id))
        usage = UsageTally()
        started = time.perf_counter()
        # 2. e 3.
        result: QaResult
        if await self._budget.exceeded():
            result = degraded_result(assistant_id)
        else:
            try:
                result = await self._workflow.run(
                    question,
                    history=history,
                    visitor_type=None,
                    request_id=request_id,
                    run_id=assistant_id,
                    trace_metadata=self._trace_metadata(contact, conversation_id),
                    usage=usage,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _LOG.warning("whatsapp.question_failed", error_type=type(exc).__name__)
                result = error_result(assistant_id)
        latency_ms = max(0, int((time.perf_counter() - started) * 1000))
        offer = await self._offer(result)
        reply = to_whatsapp_text(
            result.text,
            [citation.document_title for citation in result.citations],
            prefix=AI_PREFIX,
        )
        outgoing = [
            *notice,
            _Outgoing(kind=OutboundKind.TEXT, payload={"text": reply}, message_id=assistant_id),
            *offer,
        ]
        # 4.
        now = self._clock.now()
        try:
            async with open_session(self._database_url) as session, UnitOfWork(session):
                conversations = ConversationRepository(session)
                created_at = await conversations.allocate_created_at(conversation_id, now)
                await conversations.insert_message(
                    message_id=uuid4(),
                    conversation_id=conversation_id,
                    client_message_id=_client_message_id(event),
                    role="user",
                    content=stored_user_content(intent=result.intent, text=question),
                    citations=(),
                    model=None,
                    prompt_version=None,
                    input_tokens=0,
                    output_tokens=0,
                    latency_ms=None,
                    outcome=None,
                    langsmith_run_id=None,
                    created_at=created_at,
                    request_id=request_id,
                )
                await conversations.insert_message(
                    message_id=assistant_id,
                    conversation_id=conversation_id,
                    client_message_id=None,
                    role="assistant",
                    content=result.text,
                    citations=result.citations,
                    model=result.model,
                    prompt_version=result.prompt_version,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    latency_ms=latency_ms,
                    outcome=result.outcome.value,
                    langsmith_run_id=assistant_id,
                    created_at=created_at + timedelta(microseconds=1),
                    request_id=request_id,
                )
                await self._enqueue(session, contact, conversation_id, outgoing, now)
                await self._close_event(session, event, contact, bool(notice), now)
        except IntegrityError:
            # O mesmo `wamid` já virou mensagem: outro processamento ganhou. Só fecha.
            await self._finish(event, InboundStatus.DONE)
        # 5.
        await self._budget.record(usage.input_tokens, usage.output_tokens)

    async def _offer(self, result: QaResult) -> list[_Outgoing]:
        """A oferta do atendimento depois da resposta, nos desfechos da seção 29.4."""
        trigger = handoff_offer(result.outcome.value, rated_not_helpful=False, handoff_active=False)
        if trigger is None:
            return []
        status = await self._handoffs.availability()
        if status is Availability.OPEN:
            return [_buttons(text.OFFER, [Button.OFFER_YES, Button.OFFER_NO])]
        if status is Availability.BUSY:
            return [_text(text.BUSY)]
        if status is Availability.CLOSED:
            return [_text(text.CLOSED_AVAILABILITY)]
        return []

    async def _commit_outgoing(
        self,
        event: ClaimedEvent,
        contact: ContactRecord,
        conversation_id: UUID,
        outgoing: Sequence[_Outgoing],
    ) -> None:
        """Grava as mensagens fixas e fecha o evento numa transação."""
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = WhatsAppRepository(session)
            if await repository.get_contact_by_id(contact.id) is None:
                # APAGAR DADOS acabou de remover o contato.
                await repository.finish_event(event.id, InboundStatus.DONE, now)
                return
            await self._enqueue(session, contact, conversation_id, outgoing, now)
            notice_sent = any(item.kind == OutboundKind.NOTICE for item in outgoing)
            await self._close_event(session, event, contact, notice_sent, now)

    async def _close_event(
        self,
        session: AsyncSession,
        event: ClaimedEvent,
        contact: ContactRecord,
        notice_sent: bool,
        now: datetime,
    ) -> None:
        """Grava a versão do aviso, quando ele saiu, e fecha o evento."""
        repository = WhatsAppRepository(session)
        if notice_sent:
            await repository.set_notice_version(contact.id, LEGAL_DOCUMENT_VERSION)
        await repository.finish_event(event.id, InboundStatus.DONE, now)

    async def _enqueue(
        self,
        session: AsyncSession,
        contact: ContactRecord,
        conversation_id: UUID | None,
        outgoing: Sequence[_Outgoing],
        now: datetime,
    ) -> None:
        """Grava as saídas em ordem: cada uma um microssegundo depois da anterior."""
        repository = WhatsAppRepository(session)
        for index, item in enumerate(outgoing):
            await repository.enqueue(
                contact_id=contact.id,
                kind=item.kind.value,
                payload=item.payload,
                now=now,
                order=index,
                conversation_id=conversation_id,
                message_id=item.message_id,
                handoff_id=item.handoff_id,
            )

    async def _finish(self, event: ClaimedEvent, status: InboundStatus) -> None:
        async with open_session(self._database_url) as session, UnitOfWork(session):
            await WhatsAppRepository(session).finish_event(event.id, status, self._clock.now())

    def _notice(self, contact: ContactRecord) -> list[_Outgoing]:
        """O aviso da seção 30.9.4, na primeira mensagem e a cada versão nova."""
        if contact.notice_version == LEGAL_DOCUMENT_VERSION:
            return []
        body = text.NOTICE.format(privacy_url=f"{self._web_origin}/privacy")
        return [_Outgoing(kind=OutboundKind.NOTICE, payload={"text": ai_text(body)})]

    async def _conversation(
        self, session: AsyncSession, contact: ContactRecord, now: datetime
    ) -> UUID:
        """A conversa ativa do contato, ou uma nova depois de 24 horas (seção 30.3).

        Uma conversa com atendimento ativo continua, mesmo passadas as 24 horas.
        """
        repository = WhatsAppRepository(session)
        current = await repository.active_conversation(contact.guest_key_id)
        if current is not None:
            conversation_id, last_user_at = current
            active = await HandoffRepository(session).active_for_conversation(conversation_id)
            if active is not None or not is_new_conversation(last_user_at, now):
                return conversation_id
        conversations = ConversationRepository(session)
        created = await conversations.insert_conversation(
            user_id=None,
            guest_key_id=contact.guest_key_id,
            created_at=await conversations.allocate_conversation_created_at(now),
            channel=Channel.WHATSAPP.value,
        )
        return created.id

    async def _active_handoff(self, conversation_id: UUID) -> Any:
        async with open_session(self._database_url) as session, UnitOfWork(session):
            return await HandoffRepository(session).active_for_conversation(conversation_id)

    async def _question_rate(self, contact: ContactRecord) -> tuple[bool, bool]:
        """Conta a pergunta no balde do contato. Devolve se passou e se é a primeira vez."""
        now = self._clock.now()
        window = fixed_window_start(now, QUESTION_WINDOW)
        async with open_session(self._database_url) as session, UnitOfWork(session):
            count = await RateLimitRepository(session).increment(
                bucket_key(
                    purpose=QUESTION_CONTACT_PURPOSE,
                    subject=str(contact.id),
                    day=now.astimezone(UTC).date(),
                    key=self._hmac_key,
                ),
                window,
            )
        return count > QUESTION_CONTACT_LIMIT, count == QUESTION_CONTACT_LIMIT + 1

    def _trace_metadata(self, contact: ContactRecord, conversation_id: UUID) -> TraceMetadata:
        """Metadados do LangSmith: o pseudônimo da chave interna, nunca o BSUID."""
        subject = None
        if self._pseudonym_key:
            subject = subject_pseudonym(contact.guest_key_id, self._pseudonym_key)
        return TraceMetadata(
            environment=self._app_env,
            app_version=__version__,
            conversation_id=str(conversation_id),
            subject=subject,
            channel=Channel.WHATSAPP.value,
        )

    # 2. Repasse do atendimento.

    async def relay_handoffs(self) -> int:
        """Repassa ao WhatsApp as mensagens da equipe e as mudanças de status (seção 30.5)."""
        async with open_session(self._database_url) as session, UnitOfWork(session):
            candidates = await WhatsAppRepository(session).relay_candidates()
        relayed = 0
        for handoff_id in candidates:
            if await self._relay_one(handoff_id):
                relayed += 1
        return relayed

    async def _relay_one(self, handoff_id: UUID) -> bool:
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = WhatsAppRepository(session)
            item = await repository.lock_relay(handoff_id)
            if item is None:
                return False
            handoffs = HandoffRepository(session)
            record = await handoffs.get(handoff_id)
            if record is None:
                return False
            status_changed = (
                item.announced_status != item.status
                or item.announced_assigned_at != item.assigned_at
            )
            status_message: _Outgoing | None = None
            if status_changed:
                if item.status == HandoffStatus.QUEUED:
                    position = queue_position(await handoffs.queue_ahead(record))
                    template = (
                        text.RETURNED
                        if item.announced_status == HandoffStatus.ASSIGNED
                        else text.QUEUED
                    )
                    status_message = _text(template.format(position=position), handoff_id)
                elif item.status == HandoffStatus.ASSIGNED:
                    status_message = _text(text.ASSIGNED, handoff_id)
                elif item.status == HandoffStatus.CLOSED and item.close_reason:
                    closing = text.CLOSE_TEXTS.get(item.close_reason, text.CONTINUE)
                    status_message = _text(f"{closing}\n\n{text.CONTINUE}", handoff_id)
            lines = await repository.staff_lines_after(handoff_id, item.delivered_seq)
            staff = [
                _Outgoing(
                    kind=OutboundKind.TEXT,
                    payload={"text": staff_text(line.content)},
                    message_id=line.message_id,
                    handoff_id=handoff_id,
                )
                for line in lines
            ]
            outgoing: list[_Outgoing] = []
            if status_message is not None and item.status != HandoffStatus.CLOSED:
                outgoing.append(status_message)
            outgoing.extend(staff)
            if status_message is not None and item.status == HandoffStatus.CLOSED:
                outgoing.append(status_message)
            contact = await repository.get_contact_by_id(item.contact_id)
            if contact is not None and outgoing:
                await self._enqueue(session, contact, item.conversation_id, outgoing, now)
            await repository.advance_relay(
                handoff_id,
                delivered_seq=item.last_seq,
                status=item.status,
                assigned_at=item.assigned_at,
            )
        if staff:
            self.wake()
        return bool(outgoing)

    # 3. Caixa de saída.

    async def send_next(self) -> bool:
        """Envia uma mensagem da caixa de saída. Devolve falso quando não há nenhuma vencida."""
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            job = await WhatsAppRepository(session).claim_outbound(now)
        if job is None:
            return False
        with traced_span("whatsapp.send", kind=job.kind, attempt=job.attempts + 1) as span:
            error_code = await self._send(job)
            if error_code is not None:
                span.set(error_code=error_code)
        return True

    async def _send(self, job: OutboundJob) -> int | None:
        """Envia, grava o `wamid` ou decide a próxima tentativa. Devolve o código do erro."""
        now = self._clock.now()
        # FR-33: fora da janela de 24 horas, nada sai.
        if not within_service_window(job.last_inbound_at, now):
            await self._fail(job, ERROR_WINDOW_CLOSED, now)
            return ERROR_WINDOW_CLOSED
        use_phone = job.used_phone
        try:
            wamid = await self._deliver(job, use_phone)
        except SendError as exc:
            if not use_phone and can_fallback_to_phone(job.identity, job.phone, exc.error_code):
                use_phone = True
                try:
                    wamid = await self._deliver(job, use_phone)
                except SendError as second:
                    exc = second
                else:
                    await self._sent(job, wamid, use_phone)
                    return None
            return await self._after_error(job, exc, use_phone)
        await self._sent(job, wamid, use_phone)
        return None

    async def _deliver(self, job: OutboundJob, use_phone: bool) -> str:
        recipient = recipient_for(job.identity, job.phone, use_phone=use_phone)
        body = str(job.payload.get("text", ""))
        if job.kind == OutboundKind.BUTTONS:
            buttons = [
                SendButton(id=str(item["id"]), title=str(item["title"]))
                for item in job.payload.get("buttons", [])
            ]
            return await self._channel.send_buttons(recipient, body, buttons)
        return await self._channel.send_text(recipient, body)

    async def _sent(self, job: OutboundJob, wamid: str, used_phone: bool) -> None:
        async with open_session(self._database_url) as session, UnitOfWork(session):
            await WhatsAppRepository(session).mark_sent(
                job.id, wamid=wamid, used_phone=used_phone, now=self._clock.now()
            )
        WHATSAPP_OUTBOUND.labels(kind=job.kind, status="sent").inc()
        _LOG.info("whatsapp.sent", kind=job.kind, attempt=job.attempts + 1)

    async def _after_error(self, job: OutboundJob, exc: SendError, used_phone: bool) -> int | None:
        now = self._clock.now()
        code = exc.error_code
        WHATSAPP_SEND_ERRORS.labels(
            error_code=str(code if code is not None else exc.http_status or "network")
        ).inc()
        attempts = job.attempts + 1
        if attempts >= MAX_SEND_ATTEMPTS or not is_retryable(
            http_status=exc.http_status, error_code=code
        ):
            await self._fail(job, code, now)
        else:
            async with open_session(self._database_url) as session, UnitOfWork(session):
                await WhatsAppRepository(session).mark_retry(
                    job.id,
                    next_attempt_at=now + next_attempt_delay(attempts),
                    error_code=code,
                    used_phone=used_phone,
                    now=now,
                )
        _LOG.warning(
            "whatsapp.send_failed",
            kind=job.kind,
            attempt=attempts,
            error_code=code,
            http_status=exc.http_status,
        )
        return code

    async def _fail(self, job: OutboundJob, code: int | None, now: datetime) -> None:
        async with open_session(self._database_url) as session, UnitOfWork(session):
            await WhatsAppRepository(session).mark_failed(job.id, error_code=code, now=now)
        WHATSAPP_OUTBOUND.labels(kind=job.kind, status="failed").inc()

    async def _sleep(self, queue: "asyncio.Queue[Any]") -> None:
        """Espera o aviso do webhook, um aviso do atendimento ou 2 segundos."""
        wake = asyncio.create_task(self._wake.wait())
        notice = asyncio.create_task(queue.get())
        try:
            await asyncio.wait(
                {wake, notice}, timeout=WAKE_INTERVAL_SECONDS, return_when=asyncio.FIRST_COMPLETED
            )
        finally:
            for task in (wake, notice):
                task.cancel()
            self._wake.clear()
            while not queue.empty():
                queue.get_nowait()


def _text(body: str, handoff_id: UUID | None = None) -> _Outgoing:
    """Um texto fixo do Atrium, com o rótulo da IA."""
    return _Outgoing(kind=OutboundKind.TEXT, payload={"text": ai_text(body)}, handoff_id=handoff_id)


def _buttons(body: str, buttons: Sequence[Button]) -> _Outgoing:
    """Uma mensagem com botões. Os títulos vêm de `prompts/whatsapp.py`."""
    return _Outgoing(
        kind=OutboundKind.BUTTONS,
        payload={
            "text": ai_text(body),
            "buttons": [{"id": item.value, "title": text.BUTTON_TITLES[item]} for item in buttons],
        },
    )


def _client_message_id(event: ClaimedEvent) -> UUID:
    """Um id estável por mensagem da Meta: o mesmo `wamid` nunca grava duas perguntas."""
    return uuid5(NAMESPACE_URL, f"whatsapp:{event.wamid or event.id}")


def _turns(rows: Sequence[MessageRecord]) -> tuple[ConversationTurn, ...]:
    """O histórico para o modelo, só com a conversa com a IA (FR-21)."""
    turns: list[ConversationTurn] = []
    for row in ai_messages(rows):
        if row.role == "user":
            turns.append(ConversationTurn(role="user", content=row.content))
        elif row.role == "assistant":
            turns.append(ConversationTurn(role="assistant", content=row.content))
    return tuple(turns)
