"""Fila de pedidos de titular do admin contra o PostgreSQL. Etapa 7.3, CA-1 e CA-2.

Seções 11.5, 12 e 15.5 do SDD (FR-16). O banco pode ter pedidos de outros testes, então
as asserções olham só os pedidos criados aqui e a ordem relativa da fila inteira.
"""

import asyncio
from collections.abc import Coroutine, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.adapters.password_hasher import get_password_hasher
from app.core.container import get_clock, get_settings
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.legal import LEGAL_DOCUMENT_VERSION
from app.main import create_app
from app.prompts.privacy import NOTE_REQUIRED, REQUEST_CLOSED, STATUS_INVALID

pytestmark = pytest.mark.integration

ORIGIN = "http://localhost:5173"
HMAC_KEY = "test-hmac-key"
PASSWORD = "correct-horse-1"
NOW = datetime(2032, 5, 20, 12, 0, tzinfo=UTC)
DAY = timedelta(days=1)
NOTE = "Conta apagada e titular avisado por e-mail."


class FrozenClock:
    def now(self) -> datetime:
        return NOW


@dataclass
class _World:
    client: TestClient
    database_url: str
    admin_id: UUID
    member_email: str
    on_time: UUID
    late_in_progress: UUID
    most_late: UUID
    closed: UUID
    users: list[UUID]


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, migrated_database: str) -> Iterator[_World]:
    monkeypatch.setenv("DATABASE_URL", migrated_database)
    monkeypatch.setenv("RATE_LIMIT_HMAC_KEY", HMAC_KEY)
    monkeypatch.setenv("WEB_ORIGIN", ORIGIN)
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("APP_AI_ADAPTER", "fake")
    get_settings.cache_clear()
    application = create_app()
    application.dependency_overrides[get_clock] = FrozenClock
    built = _run(_build(migrated_database))
    client = TestClient(application)
    _login(client, built["admin_email"])
    try:
        yield _World(client=client, database_url=migrated_database, **built["ids"])
    finally:
        _run(_cleanup(migrated_database, built))
        get_settings.cache_clear()


def test_overdue_requests_come_first_with_text_status(world: _World) -> None:
    """CA-1: os atrasados aparecem primeiro e vêm marcados como atrasados (FR-16)."""
    response = world.client.get("/v1/admin/privacy/requests")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["generated_at"].startswith("2032-05-20T12:00:00")
    items = body["requests"]
    mine = [item for item in items if UUID(item["id"]) in _ids(world)]
    assert [UUID(item["id"]) for item in mine] == [
        world.most_late,
        world.late_in_progress,
        world.on_time,
        world.closed,
    ]
    assert [item["overdue"] for item in mine] == [True, True, False, False]
    late = mine[0]
    assert late["status"] == "open"
    assert late["contact_email"] == "titular-late@example.com"
    assert late["description"] == "Quero apagar a minha conta."
    assert late["linked_account"] is True
    assert mine[1]["linked_account"] is False
    assert mine[3]["closed_at"].startswith("2032-05-19T12:00:00")
    assert mine[3]["resolution_note"] == "Respondido."

    # Na fila inteira, atrasados antes dos abertos no prazo, e abertos antes dos fechados.
    rank = [_rank(item) for item in items]
    assert rank == sorted(rank)


def test_updating_the_status_records_dsr_update(world: _World) -> None:
    """CA-2: atualizar o status grava `dsr.update`, sem a nota nem o e-mail."""
    url = f"/v1/admin/privacy/requests/{world.on_time}"
    started = _patch(world.client, url, {"status": "in_progress"})
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "in_progress"
    assert started.json()["closed_at"] is None
    assert _run(_audit(world.database_url, world.admin_id)) == [
        ("dsr.update", "data_subject_request", str(world.on_time), "open->in_progress")
    ]

    # O mesmo status, sem nota nova, não grava outro evento.
    again = _patch(world.client, url, {"status": "in_progress", "resolution_note": "  "})
    assert again.status_code == 200
    assert len(_run(_audit(world.database_url, world.admin_id))) == 1

    without_note = _patch(world.client, url, {"status": "done"})
    assert without_note.status_code == 422
    assert without_note.json()["error"]["field_errors"] == {"resolution_note": NOTE_REQUIRED}
    assert len(_run(_audit(world.database_url, world.admin_id))) == 1

    done = _patch(world.client, url, {"status": "done", "resolution_note": NOTE})
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["status"] == "done"
    assert body["resolution_note"] == NOTE
    assert body["closed_at"].startswith("2032-05-20T12:00:00")
    assert body["overdue"] is False
    events = _run(_audit(world.database_url, world.admin_id))
    # O relógio congelado dá o mesmo horário aos dois eventos; a ordem não importa aqui.
    assert sorted(event[3] or "" for event in events) == ["in_progress->done", "open->in_progress"]
    assert all(NOTE not in (event[3] or "") for event in events)
    assert _run(_row(world.database_url, world.on_time)) == ("done", NOTE, NOW)

    closed = _patch(world.client, url, {"status": "open"})
    assert closed.status_code == 409
    assert closed.json()["error"]["message"] == REQUEST_CLOSED
    assert len(_run(_audit(world.database_url, world.admin_id))) == 2


def test_rejecting_an_overdue_request_takes_it_off_the_overdue_list(world: _World) -> None:
    url = f"/v1/admin/privacy/requests/{world.most_late}"
    rejected = _patch(
        world.client,
        url,
        {"status": "rejected", "resolution_note": "Pedido duplicado do mesmo titular."},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["overdue"] is False
    items = world.client.get("/v1/admin/privacy/requests").json()["requests"]
    mine = [UUID(item["id"]) for item in items if UUID(item["id"]) in _ids(world)]
    assert mine == [world.late_in_progress, world.on_time, world.most_late, world.closed]


def test_invalid_values_unknown_ids_and_bad_origin(world: _World) -> None:
    url = f"/v1/admin/privacy/requests/{world.on_time}"
    bogus = _patch(world.client, url, {"status": "archived"})
    assert bogus.status_code == 422
    assert bogus.json()["error"]["field_errors"] == {"status": STATUS_INVALID}
    too_long = _patch(
        world.client, url, {"status": "in_progress", "resolution_note": "x" * 2001}
    )
    assert too_long.status_code == 422
    assert "resolution_note" in too_long.json()["error"]["field_errors"]
    extra = _patch(world.client, url, {"status": "in_progress", "user_id": str(uuid4())})
    assert extra.status_code == 422
    missing = _patch(world.client, f"/v1/admin/privacy/requests/{uuid4()}", {"status": "done"})
    assert missing.status_code == 404
    foreign = world.client.patch(
        url, headers={"Origin": "https://evil.example"}, json={"status": "in_progress"}
    )
    assert foreign.status_code == 403
    assert foreign.json()["error"]["code"] == "bad_origin"
    assert _run(_audit(world.database_url, world.admin_id)) == []


def test_a_member_gets_403_and_a_visitor_401(world: _World) -> None:
    member = TestClient(world.client.app)
    _login(member, world.member_email)
    url = f"/v1/admin/privacy/requests/{world.on_time}"
    assert member.get("/v1/admin/privacy/requests").status_code == 403
    assert _patch(member, url, {"status": "in_progress"}).status_code == 403
    visitor = TestClient(world.client.app)
    assert visitor.get("/v1/admin/privacy/requests").status_code == 401
    assert _patch(visitor, url, {"status": "in_progress"}).status_code == 401
    assert _run(_row(world.database_url, world.on_time))[0] == "open"


def _ids(world: _World) -> set[UUID]:
    return {world.on_time, world.late_in_progress, world.most_late, world.closed}


def _rank(item: dict[str, Any]) -> tuple[int, float]:
    """Atrasados, depois abertos no prazo (prazo crescente), depois fechados (mais novo antes)."""
    due = datetime.fromisoformat(item["due_at"]).timestamp()
    if item["overdue"]:
        return (0, due)
    if item["status"] in {"open", "in_progress"}:
        return (1, due)
    return (2, -datetime.fromisoformat(item["closed_at"]).timestamp())


def _patch(client: TestClient, url: str, body: dict[str, Any]) -> Any:
    return client.patch(url, headers={"Origin": ORIGIN}, json=body)


def _login(client: TestClient, email: str) -> None:
    response = client.post(
        "/v1/auth/login",
        headers={"Origin": ORIGIN, "X-Forwarded-For": f"dsr-{uuid4().hex}"},
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text


def _run(coro: Coroutine[object, object, Any]) -> Any:
    return asyncio.run(coro)


async def _exec(session: Any, sql: str, **params: Any) -> None:
    await session.execute(text(sql), params)


async def _build(database_url: str) -> dict[str, Any]:
    tag = uuid4().hex
    hashed = get_password_hasher().hash_password(PASSWORD)
    admin, member = uuid4(), uuid4()
    on_time, late_in_progress, most_late, closed = (uuid4() for _ in range(4))
    async with open_session(database_url) as session, UnitOfWork(session):
        for user_id, email, role in (
            (admin, f"dsr-admin-{tag}@example.com", "admin"),
            (member, f"dsr-member-{tag}@example.com", "member"),
        ):
            await _exec(
                session,
                "INSERT INTO users (id, email, password_hash, full_name, role, created_at, "
                "updated_at) VALUES (:id, :email, :hash, 'Pessoa Teste', :role, :now, :now)",
                id=user_id, email=email, hash=hashed, role=role, now=NOW,
            )
            await _exec(
                session,
                "INSERT INTO consent_records (user_id, purpose, document_version, granted_at, "
                "source) VALUES (:id, 'terms_and_privacy_notice', :version, :now, 'form')",
                id=user_id, version=LEGAL_DOCUMENT_VERSION, now=NOW - 30 * DAY,
            )
        rows: tuple[tuple[UUID, UUID | None, str, str, datetime, str | None, datetime | None], ...]
        rows = (
            (on_time, None, "titular-ok@example.com", "open", NOW + 10 * DAY, None, None),
            (late_in_progress, None, "titular-mid@example.com", "in_progress", NOW - 2 * DAY,
             None, None),
            (most_late, member, "titular-late@example.com", "open", NOW - 5 * DAY, None, None),
            (closed, None, "titular-closed@example.com", "done", NOW - 9 * DAY, "Respondido.",
             NOW - DAY),
        )
        for request_id, owner, email, status, due, note, closed_at in rows:
            await _exec(
                session,
                "INSERT INTO data_subject_requests (id, user_id, contact_email, request_type, "
                "description, status, received_at, due_at, closed_at, resolution_note) "
                "VALUES (:id, :user_id, :email, 'deletion', 'Quero apagar a minha conta.', "
                ":status, :received, :due, :closed_at, :note)",
                id=request_id, user_id=owner, email=email, status=status,
                received=due - timedelta(days=15), due=due, closed_at=closed_at, note=note,
            )
    return {
        "admin_email": f"dsr-admin-{tag}@example.com",
        "ids": {
            "admin_id": admin,
            "member_email": f"dsr-member-{tag}@example.com",
            "on_time": on_time,
            "late_in_progress": late_in_progress,
            "most_late": most_late,
            "closed": closed,
            "users": [admin, member],
        },
        "requests": [on_time, late_in_progress, most_late, closed],
    }


async def _audit(database_url: str, actor: UUID) -> list[tuple[str, str, str, str | None]]:
    async with open_session(database_url) as session:
        result = await session.execute(
            text(
                "SELECT action, target_type, target_id::text, reason FROM audit_events "
                "WHERE actor_user_id = :actor ORDER BY created_at, reason"
            ),
            {"actor": actor},
        )
    return [(str(row[0]), str(row[1]), str(row[2]), row[3]) for row in result.all()]


async def _row(database_url: str, request_id: UUID) -> tuple[str, str | None, datetime | None]:
    async with open_session(database_url) as session:
        result = await session.execute(
            text(
                "SELECT status, resolution_note, closed_at FROM data_subject_requests "
                "WHERE id = :id"
            ),
            {"id": request_id},
        )
        row = result.one()
    return str(row[0]), row[1], row[2]


async def _cleanup(database_url: str, built: dict[str, Any]) -> None:
    async with open_session(database_url) as session, UnitOfWork(session):
        await _exec(
            session,
            "DELETE FROM data_subject_requests WHERE id = ANY(:ids)",
            ids=built["requests"],
        )
        for user_id in built["ids"]["users"]:
            await _exec(session, "DELETE FROM audit_events WHERE actor_user_id = :id", id=user_id)
            await _exec(session, "DELETE FROM auth_sessions WHERE user_id = :id", id=user_id)
            await _exec(session, "DELETE FROM consent_records WHERE user_id = :id", id=user_id)
            await _exec(session, "DELETE FROM users WHERE id = :id", id=user_id)
