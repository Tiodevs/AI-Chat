"""Regras puras da fila de pedidos de titular do admin. Seções 11.5 e 12, Etapa 7.3."""

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.privacy import (
    RESOLUTION_NOTE_MAX_CHARS,
    RequestStatus,
    UpdateProblem,
    is_overdue,
    plan_update,
    transition_reason,
)

NOW = datetime(2031, 3, 10, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("status", "due", "expected"),
    [
        ("open", NOW - timedelta(seconds=1), True),
        ("in_progress", NOW - timedelta(days=3), True),
        ("open", NOW, False),
        ("open", NOW + timedelta(days=1), False),
        ("done", NOW - timedelta(days=30), False),
        ("rejected", NOW - timedelta(days=30), False),
    ],
)
def test_only_open_requests_past_the_due_date_are_overdue(
    status: str, due: datetime, expected: bool
) -> None:
    assert is_overdue(status=status, due_at=due, now=NOW) is expected


def test_moving_to_in_progress_keeps_the_request_open() -> None:
    change, problem = plan_update(
        current_status="open",
        current_note=None,
        status="in_progress",
        resolution_note=None,
        now=NOW,
    )
    assert problem is None
    assert change is not None
    assert change.status == "in_progress"
    assert change.closed_at is None
    assert change.resolution_note is None
    assert change.changed is True


@pytest.mark.parametrize("closing", [RequestStatus.DONE.value, RequestStatus.REJECTED.value])
def test_closing_needs_a_note_and_records_the_closing_time(closing: str) -> None:
    missing, problem = plan_update(
        current_status="in_progress",
        current_note=None,
        status=closing,
        resolution_note="   ",
        now=NOW,
    )
    assert missing is None
    assert problem is UpdateProblem.NOTE_REQUIRED

    change, problem = plan_update(
        current_status="in_progress",
        current_note=None,
        status=closing,
        resolution_note="  Dados apagados e titular avisado por e-mail.  ",
        now=NOW,
    )
    assert problem is None
    assert change is not None
    assert change.resolution_note == "Dados apagados e titular avisado por e-mail."
    assert change.closed_at == NOW


def test_a_note_already_saved_is_enough_to_close() -> None:
    change, problem = plan_update(
        current_status="in_progress",
        current_note="Conta localizada.",
        status="done",
        resolution_note=None,
        now=NOW,
    )
    assert problem is None
    assert change is not None
    assert change.resolution_note == "Conta localizada."


@pytest.mark.parametrize("closed", ["done", "rejected"])
def test_a_closed_request_does_not_change_again(closed: str) -> None:
    change, problem = plan_update(
        current_status=closed,
        current_note="Feito.",
        status="open",
        resolution_note=None,
        now=NOW,
    )
    assert change is None
    assert problem is UpdateProblem.CLOSED


def test_unknown_status_and_long_note_are_field_problems() -> None:
    _, unknown = plan_update(
        current_status="open", current_note=None, status="archived", resolution_note=None, now=NOW
    )
    assert unknown is UpdateProblem.STATUS_INVALID
    _, too_long = plan_update(
        current_status="open",
        current_note=None,
        status="in_progress",
        resolution_note="x" * (RESOLUTION_NOTE_MAX_CHARS + 1),
        now=NOW,
    )
    assert too_long is UpdateProblem.NOTE_TOO_LONG


def test_the_same_status_and_note_is_not_a_change() -> None:
    change, problem = plan_update(
        current_status="in_progress",
        current_note="Conta localizada.",
        status="in_progress",
        resolution_note="Conta localizada.",
        now=NOW,
    )
    assert problem is None
    assert change is not None
    assert change.changed is False
    noted, _ = plan_update(
        current_status="in_progress",
        current_note="Conta localizada.",
        status="in_progress",
        resolution_note="Aguardando confirmação do titular.",
        now=NOW,
    )
    assert noted is not None
    assert noted.changed is True


def test_the_audit_reason_carries_only_the_status_change() -> None:
    assert transition_reason("open", "in_progress") == "open->in_progress"
