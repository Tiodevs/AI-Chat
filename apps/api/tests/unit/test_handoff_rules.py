"""Regras puras do atendimento humano. FR-19 e seções 29.4, 29.5, 29.8 e 29.14 do SDD.

Testa `app/domain/handoff.py` sem banco, rede nem modelo: a máquina de estados do diagrama da
seção 29.5, a tabela da oferta, a disponibilidade, a presença, o bloqueio por abuso, o texto
das mensagens, o rótulo e a carga do `NOTIFY`.
"""

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.domain.errors import Conflict
from app.domain.handoff import (
    ATTENDANT_CLOSE_REASONS,
    MAX_STAFF_CHARS,
    MAX_VISITOR_CHARS,
    Availability,
    CloseReason,
    HandoffStatus,
    HandoffTrigger,
    NoticeKind,
    availability,
    clean_message,
    close_reason_for_visitor,
    handoff_label_code,
    handoff_offer,
    has_capacity,
    is_blocked,
    is_present,
    notify_payload,
    queue_position,
    transition,
)

NOW = datetime(2026, 11, 12, 15, 0, tzinfo=UTC)
HANDOFF = UUID("00000000-0000-4000-8000-0000000000a1")


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (HandoffStatus.QUEUED, HandoffStatus.ASSIGNED),
        (HandoffStatus.ASSIGNED, HandoffStatus.QUEUED),
        (HandoffStatus.QUEUED, HandoffStatus.CLOSED),
        (HandoffStatus.ASSIGNED, HandoffStatus.CLOSED),
    ],
)
def test_transitions_of_the_diagram_pass(current: HandoffStatus, target: HandoffStatus) -> None:
    assert transition(current, target, conflict_message="x") is target


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (HandoffStatus.CLOSED, HandoffStatus.QUEUED),
        (HandoffStatus.CLOSED, HandoffStatus.ASSIGNED),
        (HandoffStatus.CLOSED, HandoffStatus.CLOSED),
        (HandoffStatus.QUEUED, HandoffStatus.QUEUED),
        (HandoffStatus.ASSIGNED, HandoffStatus.ASSIGNED),
    ],
)
def test_transitions_outside_the_diagram_raise_conflict(
    current: HandoffStatus, target: HandoffStatus
) -> None:
    # CA-1 da Etapa 17.1.
    with pytest.raises(Conflict) as raised:
        transition(current, target, conflict_message="Este atendimento já foi encerrado.")
    assert raised.value.message == "Este atendimento já foi encerrado."


@pytest.mark.parametrize(
    ("outcome", "not_helpful", "expected"),
    [
        ("abstained", False, HandoffTrigger.ABSTAINED),
        ("grounding_failed", False, HandoffTrigger.GROUNDING_FAILED),
        ("off_topic", False, HandoffTrigger.OFF_TOPIC),
        ("degraded", False, HandoffTrigger.DEGRADED),
        ("error", False, HandoffTrigger.ERROR),
        ("answered", True, HandoffTrigger.NOT_HELPFUL),
        ("answered", False, None),
        ("refused", False, None),
        ("refused", True, None),
        ("cancelled", False, None),
        ("cancelled", True, None),
        (None, False, None),
    ],
)
def test_offer_follows_the_table_of_section_29_4(
    outcome: str | None, not_helpful: bool, expected: HandoffTrigger | None
) -> None:
    # CA-2 da Etapa 17.1: `refused` nunca oferece, nem com a nota não útil (FR-19).
    assert handoff_offer(outcome, rated_not_helpful=not_helpful, handoff_active=False) is expected


def test_active_handoff_never_offers_another() -> None:
    assert handoff_offer("abstained", rated_not_helpful=False, handoff_active=True) is None


@pytest.mark.parametrize(
    ("enabled", "present", "queued", "expected"),
    [
        (False, 3, 0, Availability.DISABLED),
        (True, 0, 0, Availability.CLOSED),
        (True, 0, 20, Availability.CLOSED),
        (True, 1, 20, Availability.BUSY),
        (True, 1, 19, Availability.OPEN),
    ],
)
def test_availability(enabled: bool, present: int, queued: int, expected: Availability) -> None:
    assert availability(enabled=enabled, attendants_present=present, queued=queued) is expected


def test_presence_needs_available_and_a_signal_in_45_seconds() -> None:
    assert is_present("available", NOW - timedelta(seconds=45), NOW)
    assert not is_present("available", NOW - timedelta(seconds=46), NOW)
    assert not is_present("away", NOW, NOW)


def test_queue_position_counts_the_requests_ahead() -> None:
    assert queue_position(0) == 1
    assert queue_position(4) == 5


def test_abusive_close_blocks_for_24_hours() -> None:
    assert is_blocked(NOW - timedelta(hours=23, minutes=59), NOW)
    assert not is_blocked(NOW - timedelta(hours=24), NOW)
    assert not is_blocked(None, NOW)


def test_capacity_is_three_handoffs() -> None:
    assert has_capacity(2)
    assert not has_capacity(3)


def test_visitor_close_reason_depends_on_the_status() -> None:
    assert close_reason_for_visitor("queued") is CloseReason.VISITOR_CANCELLED
    assert close_reason_for_visitor("assigned") is CloseReason.VISITOR_ENDED


def test_staff_closes_only_with_reasons_of_the_closed_list() -> None:
    assert {reason.value for reason in ATTENDANT_CLOSE_REASONS} == {
        "resolved",
        "redirected",
        "out_of_scope",
        "no_response",
        "abusive",
    }


def test_message_text_limits_and_control_characters() -> None:
    assert clean_message("Olá\r\nTudo bem?\tSim", MAX_VISITOR_CHARS) == "Olá\nTudo bem?\tSim"
    assert clean_message("a" * MAX_VISITOR_CHARS, MAX_VISITOR_CHARS) is not None
    assert clean_message("a" * (MAX_VISITOR_CHARS + 1), MAX_VISITOR_CHARS) is None
    assert clean_message("a" * MAX_STAFF_CHARS, MAX_STAFF_CHARS) is not None
    assert clean_message("   \n ", MAX_VISITOR_CHARS) is None
    assert clean_message("com\x00nulo", MAX_VISITOR_CHARS) is None
    assert clean_message("com\x1bescape", MAX_VISITOR_CHARS) is None


def test_label_comes_from_the_handoff_id_and_has_8_characters() -> None:
    code = handoff_label_code(HANDOFF, "pseudonym-key")
    assert len(code) == 8
    assert code == handoff_label_code(HANDOFF, "pseudonym-key")
    assert code != handoff_label_code(UUID(int=HANDOFF.int + 1), "pseudonym-key")
    assert handoff_label_code(HANDOFF, "") == HANDOFF.hex[:8]


def test_notify_payload_has_only_ids_and_fits_200_bytes() -> None:
    payload = notify_payload(HANDOFF, 12, NoticeKind.MESSAGE)
    assert json.loads(payload) == {"handoff_id": str(HANDOFF), "seq": 12, "kind": "message"}
    assert len(payload.encode("utf-8")) < 200
