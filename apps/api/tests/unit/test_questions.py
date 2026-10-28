"""Regras puras da pergunta por HTTP. Seções 7.1, 8.1 e 10.4."""

from datetime import UTC, datetime
from uuid import uuid4

from app.domain.auth import fixed_window_start
from app.domain.outcomes import OUTCOME_CHECK_SQL, Outcome
from app.domain.questions import (
    DIAGNOSTICS_WINDOW,
    GUEST_COOKIE_NAME,
    GUEST_MAX_AGE_SECONDS,
    HEALTH_MESSAGE_MARKER,
    QUESTION_WINDOW,
    diagnostics_rate_decision,
    guest_cookie,
    guest_question_rate_decision,
    member_question_rate_decision,
    owns_conversation,
    stored_user_content,
)

NOW = datetime(2026, 10, 27, 12, 7, tzinfo=UTC)


def test_medical_intent_is_stored_as_the_marker() -> None:
    assert (
        stored_user_content(intent="medical_advice", text="Estou com dor no peito")
        == HEALTH_MESSAGE_MARKER
    )
    assert stored_user_content(intent="public_info", text="horário") == "horário"
    assert (
        stored_user_content(intent=None, text="Estou com dor no peito") == "Estou com dor no peito"
    )


def test_only_the_matching_owner_can_access() -> None:
    user = uuid4()
    guest = uuid4()
    other = uuid4()
    assert owns_conversation(
        actor_user_id=user,
        actor_guest_key_id=None,
        owner_user_id=user,
        owner_guest_key_id=None,
    )
    assert owns_conversation(
        actor_user_id=None,
        actor_guest_key_id=guest,
        owner_user_id=None,
        owner_guest_key_id=guest,
    )
    assert owns_conversation(
        actor_user_id=user,
        actor_guest_key_id=guest,
        owner_user_id=None,
        owner_guest_key_id=guest,
    )
    assert not owns_conversation(
        actor_user_id=other,
        actor_guest_key_id=None,
        owner_user_id=user,
        owner_guest_key_id=None,
    )
    assert not owns_conversation(
        actor_user_id=None,
        actor_guest_key_id=other,
        owner_user_id=None,
        owner_guest_key_id=guest,
    )


def test_guest_cookie_is_host_only_and_lasts_thirty_days() -> None:
    local = guest_cookie(secret="segredo", app_env="local")
    assert local.name == GUEST_COOKIE_NAME == "atrium_guest"
    assert local.http_only is True
    assert local.same_site == "lax"
    assert local.secure is False
    assert local.path == "/"
    assert local.max_age == GUEST_MAX_AGE_SECONDS == 30 * 24 * 60 * 60
    assert guest_cookie(secret="segredo", app_env="production").secure is True


def test_question_buckets_open_at_the_limit_and_close_above_it() -> None:
    question_window = fixed_window_start(NOW, QUESTION_WINDOW)
    diagnostics_window = fixed_window_start(NOW, DIAGNOSTICS_WINDOW)
    assert not guest_question_rate_decision(
        key_count=30,
        ip_count=60,
        now=NOW,
        window_start=question_window,
    ).limited
    limited = guest_question_rate_decision(
        key_count=31,
        ip_count=1,
        now=NOW,
        window_start=question_window,
    )
    assert limited.limited is True
    assert limited.retry_after_seconds == 3180
    assert not member_question_rate_decision(
        user_count=120,
        now=NOW,
        window_start=question_window,
    ).limited
    assert member_question_rate_decision(
        user_count=121,
        now=NOW,
        window_start=question_window,
    ).retry_after_seconds == 3180
    assert not diagnostics_rate_decision(
        ip_count=60,
        now=NOW,
        window_start=diagnostics_window,
    ).limited
    assert diagnostics_rate_decision(
        ip_count=61,
        now=NOW,
        window_start=diagnostics_window,
    ).retry_after_seconds == 3180


def test_outcome_check_lists_every_outcome() -> None:
    for outcome in Outcome:
        assert f"'{outcome.value}'" in OUTCOME_CHECK_SQL
