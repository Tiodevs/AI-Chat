"""Canal WhatsApp contra o PostgreSQL da CI, sem Gemini, sem LangSmith e sem a Meta. Seção 30.

O webhook roda pela API real (`create_app` com o canal ligado). O laço do canal roda direto,
com o `FakeMessagingChannel` no lugar da Graph API e um workflow falso no lugar do pipeline:
o teste escolhe o `QaResult` e confere o que foi gravado e o que seria enviado (NFR-24).
"""

import asyncio
import hashlib
import hmac
import json
from collections.abc import Coroutine, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.fake_messaging import FakeMessagingChannel
from app.adapters.realtime import InMemoryBroker
from app.core.container import get_clock, get_settings
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.grounding import Citation
from app.domain.handoff import StaffMember
from app.domain.outcomes import Outcome
from app.domain.questions import HEALTH_MESSAGE_MARKER
from app.domain.retention import RetentionRule
from app.domain.whatsapp import AI_PREFIX, STAFF_PREFIX, Button
from app.main import create_app
from app.models.conversation import Conversation
from app.models.guest_key import GuestKey
from app.models.handoff import Handoff
from app.models.message import Message
from app.models.whatsapp import (
    WhatsAppContact,
    WhatsAppInboundEvent,
    WhatsAppOutboundMessage,
)
from app.ports.messaging import SendError
from app.prompts import whatsapp as copy
from app.repositories.handoffs import HandoffRepository
from app.services.attendance import AttendanceService
from app.services.handoff import HandoffService
from app.services.retention import RetentionService
from app.services.whatsapp import WhatsAppWorker
from app.services.whatsapp_webhook import WhatsAppWebhookService
from app.workflows.qa import QaResult
from tests.integration.test_auth import HMAC_KEY
from tests.integration.test_handoff import (
    NOW,
    ORIGIN,
    PSEUDONYM_KEY,
    MovingClock,
    People,
    _acknowledge,
    _staff_member,
)

pytestmark = pytest.mark.integration

APP_SECRET = "whatsapp-app-secret"
VERIFY_TOKEN = "whatsapp-verify-token"
PHONE_ID = "555000111"


@dataclass
class FakeWorkflow:
    """O `QaWorkflow` do teste: devolve o resultado escolhido e guarda as perguntas."""

    result: QaResult | None = None
    calls: list[tuple[str, tuple[Any, ...]]] = field(default_factory=list)

    async def run(self, question: str, *, history: Sequence[Any] = (), **_: Any) -> QaResult:
        self.calls.append((question, tuple(history)))
        assert self.result is not None
        return self.result


class FreeBudget:
    """Orçamento sem teto, sem gravar nada."""

    async def exceeded(self) -> bool:
        return False

    async def record(self, input_tokens: int, output_tokens: int) -> None:
        return None


def _result(outcome: Outcome, text: str, *, intent: str | None = "public_info") -> QaResult:
    citations: tuple[Citation, ...] = ()
    if outcome is Outcome.ANSWERED:
        citations = (Citation(index=1, document_title="Visitas", heading=None, chunk_id=uuid4()),)
    return QaResult(
        outcome=outcome,
        text=text,
        citations=citations,
        input_tokens=10,
        output_tokens=5,
        model="fake-chat",
        prompt_version="qa-test",
        intent=intent,
        confidence=0.9,
        standalone_question=None,
        run_id=uuid4(),
    )


@dataclass
class Harness:
    """O laço do canal com as peças falsas, mais o serviço do webhook."""

    worker: WhatsAppWorker
    webhook: WhatsAppWebhookService
    channel: FakeMessagingChannel
    workflow: FakeWorkflow
    clock: MovingClock
    broker: InMemoryBroker
    database_url: str
    identities: list[str] = field(default_factory=list)

    def bsuid(self) -> str:
        identity = f"BR.{uuid4().hex}"
        self.identities.append(identity)
        return identity

    def receive(self, payload: dict[str, Any]) -> int:
        body = json.dumps(payload).encode()
        return _run(self.webhook.receive(body, _sign(body), "203.0.113.9"))

    def turn(self) -> None:
        _run(self.worker.run_once())


@pytest.fixture
def harness(migrated_database: str) -> Iterator[Harness]:
    clock = MovingClock(NOW)
    broker = InMemoryBroker()
    channel = FakeMessagingChannel()
    workflow = FakeWorkflow()
    handoffs = HandoffService(
        database_url=migrated_database,
        clock=clock,
        hmac_key=HMAC_KEY,
        enabled=True,
        broker=broker,
    )
    worker = WhatsAppWorker(
        database_url=migrated_database,
        clock=clock,
        channel=channel,
        workflow=workflow,  # type: ignore[arg-type]
        budget=FreeBudget(),
        handoffs=handoffs,
        broker=broker,
        hmac_key=HMAC_KEY,
        pseudonym_key=PSEUDONYM_KEY,
        app_env="test",
        web_origin=ORIGIN,
    )
    webhook = WhatsAppWebhookService(
        database_url=migrated_database,
        clock=clock,
        app_secret=APP_SECRET,
        verify_token=VERIFY_TOKEN,
        phone_number_id=PHONE_ID,
        hmac_key=HMAC_KEY,
        wake=worker.wake,
    )
    created = Harness(
        worker=worker,
        webhook=webhook,
        channel=channel,
        workflow=workflow,
        clock=clock,
        broker=broker,
        database_url=migrated_database,
    )
    yield created
    _run(_cleanup(migrated_database, created.identities))


@pytest.fixture
def accounts(migrated_database: str) -> Iterator[People]:
    """As contas da equipe criadas pelo teste, apagadas no fim."""
    created = People(migrated_database)
    yield created
    _run(created.cleanup())


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch, migrated_database: str) -> Iterator[TestClient]:
    monkeypatch.setenv("DATABASE_URL", migrated_database)
    monkeypatch.setenv("RATE_LIMIT_HMAC_KEY", HMAC_KEY)
    monkeypatch.setenv("PSEUDONYM_KEY", PSEUDONYM_KEY)
    monkeypatch.setenv("WEB_ORIGIN", ORIGIN)
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("APP_AI_ADAPTER", "fake")
    monkeypatch.setenv("LLM_DAILY_TOKEN_BUDGET", "0")
    monkeypatch.setenv("WHATSAPP_ENABLED", "true")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", PHONE_ID)
    monkeypatch.setenv("WHATSAPP_APP_SECRET", APP_SECRET)
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "token")
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", VERIFY_TOKEN)
    get_settings.cache_clear()
    application = create_app()
    application.dependency_overrides[get_clock] = lambda: MovingClock(NOW)
    yield TestClient(application)
    get_settings.cache_clear()


# Webhook pela API.


def test_verification_returns_the_challenge_only_with_the_token(api: TestClient) -> None:
    ok = api.get(
        "/v1/whatsapp/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": VERIFY_TOKEN, "hub.challenge": "77"},
    )
    assert ok.status_code == 200 and ok.text == "77"
    wrong = api.get(
        "/v1/whatsapp/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "x", "hub.challenge": "77"},
    )
    assert wrong.status_code == 403


def test_signed_post_without_origin_is_stored_once(api: TestClient, migrated_database: str) -> None:
    # Etapa 18.2, CA-2 e CA-3 (NFR-21, NFR-22): sem Origin, só com a assinatura.
    identity = f"BR.{uuid4().hex}"
    wamid = f"wamid.{uuid4().hex}"
    body = json.dumps(_text_payload(identity, "oi", wamid)).encode()
    headers = {"x-hub-signature-256": _sign(body), "content-type": "application/json"}
    try:
        first = api.post("/v1/whatsapp/webhook", content=body, headers=headers)
        again = api.post("/v1/whatsapp/webhook", content=body, headers=headers)
        assert first.status_code == 200 and first.content == b""
        assert again.status_code == 200
        assert _run(_count_events(migrated_database, wamid)) == 1
    finally:
        _run(_cleanup(migrated_database, [identity]))


def test_bad_signature_is_401_and_stores_nothing(api: TestClient, migrated_database: str) -> None:
    wamid = f"wamid.{uuid4().hex}"
    body = json.dumps(_text_payload("BR.bad", "oi", wamid)).encode()
    response = api.post(
        "/v1/whatsapp/webhook",
        content=body,
        headers={"x-hub-signature-256": _sign(body, "other-secret")},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "whatsapp_bad_signature"
    assert _run(_count_events(migrated_database, wamid)) == 0


def test_other_posts_without_origin_are_still_refused(api: TestClient) -> None:
    # NFR-12: a isenção vale só para o caminho exato do webhook.
    response = api.post("/v1/conversations", json={})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "bad_origin"


def test_the_route_does_not_exist_with_the_channel_off(
    monkeypatch: pytest.MonkeyPatch, migrated_database: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_database)
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("WHATSAPP_ENABLED", "false")
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        assert client.get("/v1/whatsapp/webhook").status_code == 404
    finally:
        get_settings.cache_clear()


# O laço do canal.


def test_question_gets_the_notice_and_then_the_answer_with_sources(harness: Harness) -> None:
    # Etapa 18.3, CA-1 e CA-2 (FR-27, FR-28).
    identity = harness.bsuid()
    harness.workflow.result = _result(Outcome.ANSWERED, "As visitas vão das **10h** às 20h.")
    assert harness.receive(_text_payload(identity, "Qual o horário de visita?")) == 1
    harness.turn()
    notice, answer = harness.channel.sent
    assert notice.text.startswith(AI_PREFIX) and "APAGAR DADOS" in notice.text
    assert f"{ORIGIN}/privacy" in notice.text
    assert answer.text.startswith(AI_PREFIX)
    assert "*10h*" in answer.text and answer.text.endswith("Fontes:\n- Visitas")
    assert all(item.recipient.bsuid == identity for item in harness.channel.sent)
    assert len(harness.channel.read) == 1
    stored = _run(_contact_state(harness.database_url, identity))
    assert stored["phone"] == "5511988887777"
    assert stored["channel"] == "whatsapp"
    assert stored["roles"] == ["user", "assistant"]
    # A segunda pergunta não repete o aviso e leva o histórico.
    harness.receive(_text_payload(identity, "E no domingo?"))
    harness.turn()
    assert len(harness.channel.sent) == 3
    question, history = harness.workflow.calls[-1]
    assert question == "E no domingo?" and len(history) == 2


def test_repeated_notification_does_not_answer_twice(harness: Harness) -> None:
    identity = harness.bsuid()
    harness.workflow.result = _result(Outcome.ANSWERED, "Resposta.")
    payload = _text_payload(identity, "Pergunta")
    harness.receive(payload)
    harness.turn()
    assert harness.receive(payload) == 0
    harness.turn()
    assert len(harness.channel.sent) == 2
    assert len(harness.workflow.calls) == 1


def test_medical_question_is_stored_only_as_the_marker(harness: Harness) -> None:
    # Etapa 18.3, CA-2 (FR-29, FR-17).
    identity = harness.bsuid()
    harness.workflow.result = _result(
        Outcome.REFUSED, "Procure atendimento médico.", intent="medical_advice"
    )
    harness.receive(_text_payload(identity, "Que remédio tomo para dor de cabeça?"))
    harness.turn()
    stored = _run(_contact_state(harness.database_url, identity))
    assert stored["user_contents"] == [HEALTH_MESSAGE_MARKER]


def test_media_gets_the_fixed_text_without_the_model(harness: Harness) -> None:
    # Etapa 18.3, CA-3 (FR-31).
    identity = harness.bsuid()
    harness.receive(
        _payload([{"from_user_id": identity, "id": _wamid(), "timestamp": _ts(), "type": "image"}])
    )
    harness.turn()
    assert harness.workflow.calls == []
    assert harness.channel.sent[-1].text == f"{AI_PREFIX}\n{copy.MEDIA}"


def test_handoff_from_offer_to_staff_reply_and_end(harness: Harness, accounts: People) -> None:
    # Etapa 18.4, CA-1, CA-2 e CA-4 (FR-30, FR-21).
    staff = _ready_staff(harness, accounts)
    identity = harness.bsuid()
    harness.workflow.result = _result(Outcome.ABSTAINED, "Não encontrei essa informação.")
    harness.receive(_text_payload(identity, "Onde estaciono a moto?"))
    harness.turn()
    offer = harness.channel.sent[-1]
    assert [button.id for button in offer.buttons] == [Button.OFFER_YES, Button.OFFER_NO]
    harness.receive(_button_payload(identity, Button.OFFER_YES))
    harness.turn()
    confirm = harness.channel.sent[-1]
    assert [button.id for button in confirm.buttons] == [Button.CONFIRM_YES, Button.CONFIRM_NO]
    harness.receive(_button_payload(identity, Button.CONFIRM_YES))
    harness.turn()
    assert "Você está na fila. Posição" in harness.channel.sent[-1].text
    found = _run(_active_handoff(harness.database_url, identity))
    assert found is not None
    handoff_id: UUID = found
    # Mensagem do visitante vai para a equipe, sem identificadores e sem o modelo.
    calls = len(harness.workflow.calls)
    harness.receive(_text_payload(identity, "Meu e-mail é ana@example.com"))
    harness.turn()
    assert len(harness.workflow.calls) == calls
    assert "[e-mail removido]" in _run(_last_handoff_message(harness.database_url, handoff_id))
    # A equipe assume e responde: o repasse avisa e entrega a resposta com o rótulo.
    attendance = AttendanceService(
        database_url=harness.database_url,
        clock=harness.clock,
        hmac_key=HMAC_KEY,
        pseudonym_key=PSEUDONYM_KEY,
        broker=harness.broker,
    )
    _run(attendance.take(staff, handoff_id))
    queue = _run(attendance.queue(staff))
    assert queue.mine[0].channel == "whatsapp"
    stored = _run(
        attendance.send(
            staff,
            handoff_id,
            text="A moto fica no bloco B.",
            template=None,
            client_message_id=uuid4(),
        )
    )
    harness.turn()
    texts = [item.text for item in harness.channel.sent]
    assert f"{AI_PREFIX}\n{copy.ASSIGNED}" in texts
    staff_reply = harness.channel.sent[-1]
    assert staff_reply.text == f"{STAFF_PREFIX}\nA moto fica no bloco B."
    # O status de leitura chega pelo webhook e aparece no console.
    harness.receive(_status_payload(staff_reply.wamid, "read"))
    harness.turn()
    detail = _run(attendance.detail(staff, handoff_id))
    assert detail.deliveries[stored.id].status == "read"
    # ENCERRAR fecha o atendimento, e o repasse manda o texto de encerramento.
    harness.receive(_text_payload(identity, "encerrar"))
    harness.turn()
    assert copy.CLOSE_TEXTS["visitor_ended"] in harness.channel.sent[-1].text
    assert _run(_active_handoff(harness.database_url, identity, required=False)) is None


def test_delete_data_removes_everything_after_the_confirmation(harness: Harness) -> None:
    # Etapa 18.5, CA-1 (FR-32).
    identity = harness.bsuid()
    harness.workflow.result = _result(Outcome.ANSWERED, "Resposta.")
    harness.receive(_text_payload(identity, "Pergunta"))
    harness.turn()
    harness.receive(_text_payload(identity, "APAGAR DADOS"))
    harness.turn()
    assert [button.id for button in harness.channel.sent[-1].buttons] == [
        Button.DELETE_YES,
        Button.DELETE_NO,
    ]
    harness.receive(_button_payload(identity, Button.DELETE_NO))
    harness.turn()
    assert _run(_contact_exists(harness.database_url, identity))
    harness.receive(_button_payload(identity, Button.DELETE_YES))
    harness.turn()
    assert not _run(_contact_exists(harness.database_url, identity))
    assert harness.channel.sent[-1].text == f"{AI_PREFIX}\n{copy.DELETE_DONE}"


def test_rate_limited_send_is_retried_and_window_error_fails(harness: Harness) -> None:
    identity = harness.bsuid()
    harness.workflow.result = _result(Outcome.ANSWERED, "Resposta.")
    harness.channel.fail_with(SendError(http_status=429, error_code=None))
    harness.receive(_text_payload(identity, "Pergunta"))
    harness.turn()
    statuses = _run(_outbound_statuses(harness.database_url, identity))
    assert sorted(statuses) == ["pending", "sent"]
    harness.clock.advance(minutes=1)
    harness.channel.fail_with(SendError(http_status=400, error_code=131047))
    harness.turn()
    assert sorted(_run(_outbound_statuses(harness.database_url, identity))) == ["failed", "sent"]


def test_nothing_is_sent_outside_the_24_hour_window(harness: Harness) -> None:
    # FR-33.
    identity = harness.bsuid()
    harness.workflow.result = _result(Outcome.ANSWERED, "Resposta.")
    harness.channel.fail_with(
        SendError(http_status=503, error_code=None), SendError(http_status=503, error_code=None)
    )
    harness.receive(_text_payload(identity, "Pergunta"))
    harness.turn()
    harness.clock.advance(hours=25)
    harness.turn()
    assert all(item.recipient.bsuid != identity for item in harness.channel.sent)
    assert set(_run(_outbound_statuses(harness.database_url, identity))) == {"failed"}


def test_retention_removes_the_contact_after_30_days(harness: Harness) -> None:
    # Etapa 18.5, CA-2: a chave interna fica na regra de convidados e sai com o contato.
    identity = harness.bsuid()
    harness.workflow.result = _result(Outcome.ANSWERED, "Resposta.")
    harness.receive(_text_payload(identity, "Pergunta"))
    harness.turn()
    retention = RetentionService(
        database_url=harness.database_url, clock=MovingClock(NOW + timedelta(days=31))
    )
    _run(retention.run_rule(RetentionRule.GUEST_KEYS))
    assert _run(_contact_exists(harness.database_url, identity))
    _run(retention.run_rule(RetentionRule.WHATSAPP_CONTACTS))
    assert not _run(_contact_exists(harness.database_url, identity))


def test_logs_have_no_text_nor_identity(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    # NFR-23 e NFR-7.
    identity = harness.bsuid()
    harness.workflow.result = _result(Outcome.ANSWERED, "Resposta secreta.")
    harness.receive(_text_payload(identity, "Pergunta muito particular"))
    harness.turn()
    output = capsys.readouterr().out
    assert identity not in output
    assert "5511988887777" not in output
    assert "particular" not in output and "secreta" not in output


# Ajudantes.


def _sign(body: bytes, secret: str = APP_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _ts() -> str:
    return str(int(NOW.timestamp()))


def _wamid() -> str:
    return f"wamid.{uuid4().hex}"


def _payload(
    messages: list[dict[str, Any]], statuses: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "metadata": {"phone_number_id": PHONE_ID},
        "messages": messages,
    }
    if statuses is not None:
        value["statuses"] = statuses
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "waba", "changes": [{"field": "messages", "value": value}]}],
    }


def _text_payload(identity: str, body: str, wamid: str | None = None) -> dict[str, Any]:
    return _payload(
        [
            {
                "from": "5511988887777",
                "from_user_id": identity,
                "id": wamid or _wamid(),
                "timestamp": _ts(),
                "type": "text",
                "text": {"body": body},
            }
        ]
    )


def _button_payload(identity: str, button: Button) -> dict[str, Any]:
    return _payload(
        [
            {
                "from_user_id": identity,
                "id": _wamid(),
                "timestamp": _ts(),
                "type": "interactive",
                "interactive": {
                    "type": "button_reply",
                    "button_reply": {"id": button.value, "title": "x"},
                },
            }
        ]
    )


def _status_payload(wamid: str, status: str) -> dict[str, Any]:
    return _payload([], [{"id": wamid, "status": status, "timestamp": _ts()}])


def _ready_staff(harness: Harness, accounts: People) -> StaffMember:
    email = accounts.account("attendant")
    staff = _run(_staff_member(harness.database_url, email))
    _run(_acknowledge(harness.database_url, staff))

    async def present() -> None:
        async with open_session(harness.database_url) as session, UnitOfWork(session):
            await HandoffRepository(session).set_presence(staff.user_id, "available", NOW)

    _run(present())
    return staff


async def _cleanup(database_url: str, identities: Sequence[str]) -> None:
    async with open_session(database_url) as session, UnitOfWork(session):
        keys = select(WhatsAppContact.guest_key_id).where(
            WhatsAppContact.identity.in_(list(identities))
        )
        await session.execute(delete(GuestKey).where(GuestKey.id.in_(keys)))
        await session.execute(
            delete(WhatsAppInboundEvent).where(
                WhatsAppInboundEvent.received_at >= NOW - timedelta(days=1)
            )
        )


async def _count_events(database_url: str, wamid: str) -> int:
    async with open_session(database_url) as session, UnitOfWork(session):
        value = await session.scalar(
            select(func.count())
            .select_from(WhatsAppInboundEvent)
            .where(WhatsAppInboundEvent.event_key == wamid)
        )
    return int(value or 0)


async def _contact(session: AsyncSession, identity: str) -> WhatsAppContact | None:
    found: WhatsAppContact | None = await session.scalar(
        select(WhatsAppContact).where(WhatsAppContact.identity == identity)
    )
    return found


async def _contact_exists(database_url: str, identity: str) -> bool:
    async with open_session(database_url) as session, UnitOfWork(session):
        return await _contact(session, identity) is not None


async def _contact_state(database_url: str, identity: str) -> dict[str, Any]:
    async with open_session(database_url) as session, UnitOfWork(session):
        contact = await _contact(session, identity)
        assert contact is not None
        conversation = await session.scalar(
            select(Conversation).where(Conversation.guest_key_id == contact.guest_key_id)
        )
        assert conversation is not None
        messages = list(
            await session.scalars(
                select(Message)
                .where(Message.conversation_id == conversation.id)
                .order_by(Message.created_at)
            )
        )
        return {
            "phone": contact.phone,
            "channel": conversation.channel,
            "roles": [message.role for message in messages],
            "user_contents": [message.content for message in messages if message.role == "user"],
        }


async def _active_handoff(
    database_url: str, identity: str, *, required: bool = True
) -> UUID | None:
    async with open_session(database_url) as session, UnitOfWork(session):
        contact = await _contact(session, identity)
        assert contact is not None
        handoff_id = await session.scalar(
            select(Handoff.id)
            .join(Conversation, Conversation.id == Handoff.conversation_id)
            .where(Conversation.guest_key_id == contact.guest_key_id, Handoff.status != "closed")
        )
    if required:
        assert handoff_id is not None
    return handoff_id


async def _last_handoff_message(database_url: str, handoff_id: UUID | None) -> str:
    async with open_session(database_url) as session, UnitOfWork(session):
        content = await session.scalar(
            select(Message.content)
            .where(Message.handoff_id == handoff_id, Message.role == "user")
            .order_by(Message.seq.desc())
            .limit(1)
        )
    return str(content)


async def _outbound_statuses(database_url: str, identity: str) -> list[str]:
    async with open_session(database_url) as session, UnitOfWork(session):
        contact = await _contact(session, identity)
        assert contact is not None
        rows = await session.scalars(
            select(WhatsAppOutboundMessage.status).where(
                WhatsAppOutboundMessage.contact_id == contact.id
            )
        )
        return list(rows)


def _run[T](coroutine: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coroutine)
