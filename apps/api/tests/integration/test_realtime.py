"""Canal em tempo real do atendimento: `LISTEN/NOTIFY` e fluxos SSE com retomada.

Etapa 17.3, e a parte do fluxo do console da Etapa 17.5. FR-23, NFR-18, NFR-19, seção 29.6 e
ADR-016 do SDD. O `PostgresNotifyBroker` roda contra o PostgreSQL local, e os fluxos são lidos
direto dos serviços, num loop só, com o tique e a duração encurtados pelo `monkeypatch`, o
relógio falso destes testes. Os dados nascem pela API, com os helpers de `test_handoff.py`.
"""

import asyncio
import json
from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.adapters.realtime import InMemoryBroker, PostgresNotifyBroker
from app.core.container import get_settings
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.auth import hash_session_secret
from app.domain.handoff import HandoffNotice, NoticeKind
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.handoffs import HandoffRepository
from app.services.attendance import AttendanceService
from app.services.handoff import HandoffService
from tests.integration.test_auth import HMAC_KEY
from tests.integration.test_handoff import (
    NOW,
    PSEUDONYM_KEY,
    MovingClock,
    People,
    _guest_conversation,
    _login,
    _post,
    _request,
    _staff_member,
    _staff_ready,
    api_client,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def clock() -> MovingClock:
    return MovingClock(NOW)


@pytest.fixture
def broker() -> InMemoryBroker:
    return InMemoryBroker()


@pytest.fixture
def api(
    monkeypatch: pytest.MonkeyPatch,
    migrated_database: str,
    clock: MovingClock,
    broker: InMemoryBroker,
) -> Iterator[TestClient]:
    """A mesma API de `test_handoff.py`."""
    yield api_client(monkeypatch, migrated_database, clock, broker)
    get_settings.cache_clear()


@pytest.fixture
def people(migrated_database: str) -> Iterator[People]:
    """As contas e os convidados do teste, apagados no fim."""
    created = People(migrated_database)
    yield created
    asyncio.run(created.cleanup())


Event = tuple[str, dict[str, Any], str | None]


def test_notify_reaches_the_listener_only_after_commit(migrated_database: str) -> None:
    # CA-1 (NFR-18, ADR-016): um rollback não avisa, e a carga tem só id, `seq` e tipo.
    handoff_id = uuid4()

    async def scenario() -> tuple[list[HandoffNotice], list[HandoffNotice]]:
        listener = PostgresNotifyBroker(migrated_database)
        listener.start()
        try:
            await _until(lambda: listener.listener_up)
            queue = listener.subscribe()
            try:
                async with open_session(migrated_database) as session, UnitOfWork(session):
                    await HandoffRepository(session).notify(handoff_id, 3, NoticeKind.MESSAGE)
                    raise _Rollback
            except _Rollback:
                pass
            after_rollback = await _drain(queue, 0.5)
            async with open_session(migrated_database) as session, UnitOfWork(session):
                await HandoffRepository(session).notify(handoff_id, 4, NoticeKind.MESSAGE)
            after_commit = await _drain(queue, 2.0, stop_after=1)
            return after_rollback, after_commit
        finally:
            await listener.close()

    rolled_back, committed = asyncio.run(scenario())
    assert [notice for notice in rolled_back if notice.handoff_id == handoff_id] == []
    assert HandoffNotice(handoff_id, 4, NoticeKind.MESSAGE) in committed


def test_listener_reconnects_after_losing_the_connection(migrated_database: str) -> None:
    # CA-5 (ADR-016): o ouvinte derrubado volta, com espera crescente.
    async def scenario() -> tuple[bool, bool]:
        listener = PostgresNotifyBroker(migrated_database)
        listener.start()
        try:
            await _until(lambda: listener.server_pid is not None)
            pid = listener.server_pid
            async with open_session(migrated_database) as session, UnitOfWork(session):
                await session.execute(text("SELECT pg_terminate_backend(:pid)"), {"pid": pid})
            went_down = await _until(lambda: not listener.listener_up, timeout=5)
            came_back = await _until(
                lambda: listener.listener_up and listener.server_pid not in (None, pid),
                timeout=10,
            )
            return went_down, came_back
        finally:
            await listener.close()

    assert asyncio.run(scenario()) == (True, True)


def test_visitor_stream_resumes_after_the_last_event_id(
    api: TestClient, people: People, migrated_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # CA-2 (FR-23, NFR-19): só o que tem `seq` maior chega, e uma resposta nova acorda o
    # fluxo pelo aviso.
    monkeypatch.setattr("app.services.handoff.STREAM_TICK_SECONDS", 5.0)
    attendant = _staff_ready(api, people)
    visitor, conversation_id, answer_id = _guest_conversation(api, people)
    handoff_id = UUID(_request(visitor, conversation_id, answer_id).json()["id"])
    _post(attendant, f"/v1/attendance/handoffs/{handoff_id}/take", None)
    for index in range(3):
        _post(
            visitor,
            f"/v1/conversations/{conversation_id}/handoff/messages",
            {"text": f"mensagem {index + 1}", "client_message_id": str(uuid4())},
        )
    staff = asyncio.run(_staff_member(migrated_database, _email_of(attendant)))
    guest = visitor.cookies.get("atrium_guest")

    async def scenario() -> list[Event]:
        broker = InMemoryBroker()
        service = _handoff_service(migrated_database, broker)
        stream = await service.open_stream(
            conversation_id,
            session_secret=None,
            guest_secret=guest,
            last_event_id=f"{handoff_id}:1",
        )

        async def reply() -> None:
            await asyncio.sleep(0.3)
            await _attendance_service(migrated_database, broker).send(
                staff,
                handoff_id,
                text="Olá, posso ajudar.",
                template=None,
                client_message_id=uuid4(),
            )

        task = asyncio.create_task(reply())
        events = await _collect(stream.events, lambda found: _messages(found) >= 3)
        await task
        return events

    events = asyncio.run(scenario())
    assert events[0][0] == "ready"
    messages = [
        (payload["seq"], payload["role"], event_id)
        for name, payload, event_id in events
        if name == "message"
    ]
    assert messages == [
        (2, "user", f"{handoff_id}:2"),
        (3, "user", f"{handoff_id}:3"),
        (4, "attendant", f"{handoff_id}:4"),
    ]


def test_stream_sends_reconnect_at_the_end_of_its_duration(
    api: TestClient, people: People, migrated_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # CA-3 (NFR-19): aos 10 minutos, aqui encurtados, o fluxo manda `reconnect` e fecha.
    monkeypatch.setattr("app.services.handoff.STREAM_MAX_SECONDS", 0.6)
    monkeypatch.setattr("app.services.handoff.STREAM_TICK_SECONDS", 0.2)
    _staff_ready(api, people)
    visitor, conversation_id, answer_id = _guest_conversation(api, people)
    _request(visitor, conversation_id, answer_id)
    guest = visitor.cookies.get("atrium_guest")

    async def scenario() -> list[Event]:
        service = _handoff_service(migrated_database, InMemoryBroker())
        stream = await service.open_stream(
            conversation_id, session_secret=None, guest_secret=guest, last_event_id=None
        )
        return await _collect(stream.events, lambda found: False, timeout=5)

    names = [name for name, _payload, _id in asyncio.run(scenario())]
    assert names[0] == "ready"
    assert names[-1] == "reconnect"


def test_revoked_session_closes_the_stream_within_a_tick(
    api: TestClient, people: People, migrated_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # CA-4 (NFR-18): a sessão revogada fecha o fluxo com `error` no próximo tique.
    monkeypatch.setattr("app.services.handoff.STREAM_TICK_SECONDS", 0.2)
    _staff_ready(api, people)
    member = _login(api, people.account("member"))
    created = member.post("/v1/conversations", headers={"Origin": "http://localhost:5173"}).json()
    conversation_id = UUID(created["id"])
    from tests.integration.test_handoff import _answer

    answer_id = asyncio.run(_answer(migrated_database, conversation_id, "abstained"))
    assert _request(member, conversation_id, answer_id).status_code == 201
    secret = member.cookies.get("atrium_session")
    assert isinstance(secret, str)

    async def scenario() -> list[Event]:
        service = _handoff_service(migrated_database, InMemoryBroker())
        stream = await service.open_stream(
            conversation_id, session_secret=secret, guest_secret=None, last_event_id=None
        )

        async def revoke() -> None:
            await asyncio.sleep(0.1)
            async with open_session(migrated_database) as session, UnitOfWork(session):
                await AuthSessionRepository(session).revoke(hash_session_secret(secret), NOW)

        task = asyncio.create_task(revoke())
        events = await _collect(stream.events, lambda found: False, timeout=5)
        await task
        return events

    events = asyncio.run(scenario())
    assert events[-1][0] == "error"
    assert events[-1][1]["code"] == "unauthenticated"


def test_lost_notice_arrives_by_the_tick(
    api: TestClient, people: People, migrated_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # CA-5 (seção 29.6): sem aviso nenhum, a leitura do tique entrega a mensagem.
    monkeypatch.setattr("app.services.handoff.STREAM_TICK_SECONDS", 0.3)
    attendant = _staff_ready(api, people)
    visitor, conversation_id, answer_id = _guest_conversation(api, people)
    handoff_id = UUID(_request(visitor, conversation_id, answer_id).json()["id"])
    _post(attendant, f"/v1/attendance/handoffs/{handoff_id}/take", None)
    guest = visitor.cookies.get("atrium_guest")

    async def scenario() -> list[Event]:
        service = _handoff_service(migrated_database, _DeafBroker())
        stream = await service.open_stream(
            conversation_id, session_secret=None, guest_secret=guest, last_event_id=None
        )

        async def reply() -> None:
            await asyncio.sleep(0.1)
            # Pela API, em outro loop: o aviso nunca chega a este broker.
            await asyncio.to_thread(
                _post,
                attendant,
                f"/v1/attendance/handoffs/{handoff_id}/messages",
                {"text": "Estou aqui.", "client_message_id": str(uuid4())},
            )

        task = asyncio.create_task(reply())
        events = await _collect(stream.events, lambda found: _messages(found) >= 1, timeout=5)
        await task
        return events

    messages = [payload for name, payload, _id in asyncio.run(scenario()) if name == "message"]
    assert messages[0]["content"] == "Estou aqui."


def test_console_of_another_attendant_does_not_get_the_messages(
    api: TestClient, people: People, migrated_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Etapa 17.5, CA-3 (NFR-18): o fluxo de B não recebe as mensagens do atendimento de A.
    monkeypatch.setattr("app.services.attendance.STREAM_TICK_SECONDS", 0.3)
    monkeypatch.setattr("app.services.attendance.STREAM_MAX_SECONDS", 1.5)
    first = _staff_ready(api, people)
    second = _staff_ready(api, people)
    visitor, conversation_id, answer_id = _guest_conversation(api, people)
    handoff_id = UUID(_request(visitor, conversation_id, answer_id).json()["id"])
    _post(first, f"/v1/attendance/handoffs/{handoff_id}/take", None)
    owner = asyncio.run(_staff_member(migrated_database, _email_of(first)))
    other = asyncio.run(_staff_member(migrated_database, _email_of(second)))
    owner_secret = first.cookies.get("atrium_session")
    other_secret = second.cookies.get("atrium_session")
    guest = visitor.cookies.get("atrium_guest")

    async def scenario() -> tuple[list[Event], list[Event]]:
        broker = InMemoryBroker()
        attendance = _attendance_service(migrated_database, broker)
        handoffs = _handoff_service(migrated_database, broker)
        owner_stream = await attendance.open_console(owner, owner_secret)
        other_stream = await attendance.open_console(other, other_secret)

        async def write() -> None:
            await asyncio.sleep(0.2)
            await handoffs.send(
                conversation_id,
                text="Mensagem só para A",
                client_message_id=uuid4(),
                session_secret=None,
                guest_secret=guest,
            )

        task = asyncio.create_task(write())
        owner_events, other_events = await asyncio.gather(
            _collect(owner_stream.events, lambda found: _messages(found) >= 1, timeout=5),
            _collect(other_stream.events, lambda found: False, timeout=5),
        )
        await task
        return owner_events, other_events

    owner_events, other_events = asyncio.run(scenario())
    assert _messages(owner_events) == 1
    assert _messages(other_events) == 0
    assert "Mensagem só para A" not in json.dumps([payload for _n, payload, _i in other_events])


class _Rollback(Exception):
    """Força o rollback da `UnitOfWork` no teste do `NOTIFY`."""


class _DeafBroker(InMemoryBroker):
    """Um broker que nunca entrega aviso: o fluxo só conta com o tique."""

    async def committed(self, notices: Any) -> None:
        return None


def _handoff_service(database_url: str, broker: Any) -> HandoffService:
    """O serviço do visitante direto, com o atendimento ligado."""
    return HandoffService(
        database_url=database_url,
        clock=MovingClock(NOW),
        hmac_key=HMAC_KEY,
        enabled=True,
        broker=broker,
    )


def _attendance_service(database_url: str, broker: Any) -> AttendanceService:
    """O serviço da equipe direto."""
    return AttendanceService(
        database_url=database_url,
        clock=MovingClock(NOW),
        hmac_key=HMAC_KEY,
        pseudonym_key=PSEUDONYM_KEY,
        broker=broker,
    )


async def _collect(
    events: Callable[[asyncio.Event], AsyncIterator[str]],
    until: Callable[[list[Event]], bool],
    *,
    timeout: float = 5.0,
) -> list[Event]:
    """Lê o fluxo até `until`, até ele fechar ou até `timeout`, e devolve os eventos."""
    disconnected = asyncio.Event()
    found: list[Event] = []
    generator = events(disconnected)

    async def read() -> None:
        async for chunk in generator:
            parsed = _parse(chunk)
            if parsed is not None:
                found.append(parsed)
            if until(found):
                return

    try:
        await asyncio.wait_for(read(), timeout=timeout)
    except TimeoutError:
        pass
    finally:
        disconnected.set()
        await generator.aclose()  # type: ignore[attr-defined]
    return found


def _parse(chunk: str) -> Event | None:
    """Um pedaço SSE como (evento, carga, id). Um comentário devolve `None`."""
    name = ""
    event_id: str | None = None
    payload: dict[str, Any] | None = None
    for line in chunk.splitlines():
        if line.startswith("id: "):
            event_id = line.removeprefix("id: ")
        elif line.startswith("event: "):
            name = line.removeprefix("event: ")
        elif line.startswith("data: "):
            payload = json.loads(line.removeprefix("data: "))
    if not name or payload is None:
        return None
    return name, payload, event_id


def _messages(found: list[Event]) -> int:
    """Quantos eventos `message` chegaram."""
    return sum(1 for name, _payload, _id in found if name == "message")


async def _drain(
    queue: asyncio.Queue[HandoffNotice], seconds: float, *, stop_after: int | None = None
) -> list[HandoffNotice]:
    """Os avisos que chegam à fila em até `seconds`."""
    found: list[HandoffNotice] = []
    deadline = asyncio.get_running_loop().time() + seconds
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            return found
        try:
            found.append(await asyncio.wait_for(queue.get(), timeout=remaining))
        except TimeoutError:
            return found
        if stop_after is not None and len(found) >= stop_after:
            return found


async def _until(condition: Callable[[], bool], *, timeout: float = 5.0) -> bool:
    """Espera a condição valer, conferindo a cada 50 ms. Devolve se valeu a tempo."""
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if condition():
            return True
        await asyncio.sleep(0.05)
    return condition()


def _email_of(client: TestClient) -> str:
    """O e-mail da sessão do cliente, por `GET /v1/me`."""
    return str(client.get("/v1/me").json()["email"])
