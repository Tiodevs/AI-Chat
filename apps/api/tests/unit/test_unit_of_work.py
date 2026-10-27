import asyncio
import json
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import configure_logging
from app.db.unit_of_work import UnitOfWork


class _FakeSession:
    def __init__(self) -> None:
        self.began = False
        self.committed = False
        self.rolled_back = False
        self.closed = False

    async def begin(self) -> None:
        self.began = True

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def close(self) -> None:
        self.closed = True


def _log_events(capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    captured = capsys.readouterr().out
    return [json.loads(line) for line in captured.splitlines() if line.startswith("{")]


def test_unit_of_work_commits_and_closes() -> None:
    session = _FakeSession()

    async def _run() -> None:
        async with UnitOfWork(cast(AsyncSession, session)):
            return None

    asyncio.run(_run())
    assert session.began
    assert session.committed
    assert not session.rolled_back
    assert session.closed


def test_unit_of_work_rolls_back_when_the_body_fails() -> None:
    session = _FakeSession()

    async def _run() -> None:
        async with UnitOfWork(cast(AsyncSession, session)):
            raise RuntimeError("fail")

    with pytest.raises(RuntimeError, match="fail"):
        asyncio.run(_run())
    assert session.rolled_back
    assert not session.committed
    assert session.closed


def test_unit_of_work_warns_when_open_for_more_than_two_seconds(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_logging("INFO")
    ticks = iter((0.0, 3.5))
    monkeypatch.setattr("app.db.unit_of_work.time.perf_counter", lambda: next(ticks))
    session = _FakeSession()

    async def _run() -> None:
        async with UnitOfWork(cast(AsyncSession, session)):
            return None

    asyncio.run(_run())
    slow = [event for event in _log_events(capsys) if event.get("event") == "unit_of_work.slow"]
    assert len(slow) == 1
    assert slow[0]["level"] == "warning"
    assert slow[0]["duration_ms"] == 3500


def test_unit_of_work_stays_quiet_at_two_seconds(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_logging("INFO")
    ticks = iter((0.0, 2.0))
    monkeypatch.setattr("app.db.unit_of_work.time.perf_counter", lambda: next(ticks))

    async def _run() -> None:
        async with UnitOfWork(cast(AsyncSession, _FakeSession())):
            return None

    asyncio.run(_run())
    events = [event.get("event") for event in _log_events(capsys)]
    assert "unit_of_work.slow" not in events
