import base64
from datetime import UTC, datetime, timedelta

import pytest

from app.adapters.session_secret import new_session_secret
from app.domain.auth import (
    LOGIN_EMAIL_LIMIT,
    LOGIN_EMAIL_WINDOW,
    LOGIN_IP_LIMIT,
    LOGIN_IP_WINDOW,
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE_SECONDS,
    bucket_key,
    email_is_valid,
    fixed_window_start,
    hash_session_secret,
    login_rate_decision,
    normalize_email,
    origin_is_allowed,
    password_length_is_valid,
    retry_after_seconds,
    session_cookie,
)
from app.domain.legal import LEGAL_DOCUMENT_VERSION, needs_legal_acceptance
from app.prompts.auth import INVALID_CREDENTIALS


def test_login_error_copy_does_not_reveal_whether_the_email_exists() -> None:
    assert INVALID_CREDENTIALS == "E-mail ou senha incorretos."


def test_email_is_stored_in_lowercase() -> None:
    assert normalize_email("  Visitor@Example.com ") == "visitor@example.com"
    assert email_is_valid("visitor@example.com")
    assert not email_is_valid("not-an-email")


def test_password_length_matches_section_8_5() -> None:
    assert not password_length_is_valid("short-pass")
    assert password_length_is_valid("correct-horse")
    assert not password_length_is_valid("x" * 73)


def test_session_secret_is_256_bits_and_only_its_hash_is_stored() -> None:
    secret = new_session_secret()
    padding = "=" * (-len(secret) % 4)
    assert len(base64.urlsafe_b64decode(secret + padding)) == 32
    digest = hash_session_secret(secret)
    assert digest != secret
    assert len(digest) == 64


def test_session_cookie_is_lax_host_only_and_secure_outside_local() -> None:
    local = session_cookie(secret="secret", app_env="local")
    production = session_cookie(secret="secret", app_env="production")
    assert local.name == SESSION_COOKIE_NAME
    assert local.http_only is True
    assert local.same_site == "lax"
    assert local.path == "/"
    assert local.max_age == SESSION_MAX_AGE_SECONDS
    assert local.secure is False
    assert production.secure is True
    assert not hasattr(local, "domain")


def test_state_changing_requests_require_the_frontend_origin() -> None:
    web = "http://localhost:5173"
    assert origin_is_allowed(method="POST", origin=web, web_origin=web)
    assert not origin_is_allowed(method="POST", origin="https://evil.example", web_origin=web)
    assert not origin_is_allowed(method="DELETE", origin=None, web_origin=web)
    assert origin_is_allowed(method="GET", origin="https://evil.example", web_origin=web)


def test_fixed_window_and_retry_after() -> None:
    now = datetime(2026, 10, 27, 12, 7, 30, tzinfo=UTC)
    email_start = fixed_window_start(now, LOGIN_EMAIL_WINDOW)
    ip_start = fixed_window_start(now, LOGIN_IP_WINDOW)
    assert email_start == datetime(2026, 10, 27, 12, 0, tzinfo=UTC)
    assert ip_start == datetime(2026, 10, 27, 12, 0, tzinfo=UTC)
    assert retry_after_seconds(now, email_start, LOGIN_EMAIL_WINDOW) == 450


def test_login_limit_is_above_ten_attempts_and_thirty_per_ip() -> None:
    now = datetime(2026, 10, 27, 12, 7, tzinfo=UTC)
    email_start = fixed_window_start(now, LOGIN_EMAIL_WINDOW)
    ip_start = fixed_window_start(now, LOGIN_IP_WINDOW)
    allowed = login_rate_decision(
        email_count=LOGIN_EMAIL_LIMIT,
        ip_count=LOGIN_IP_LIMIT,
        now=now,
        email_window_start=email_start,
        ip_window_start=ip_start,
    )
    blocked = login_rate_decision(
        email_count=LOGIN_EMAIL_LIMIT + 1,
        ip_count=1,
        now=now,
        email_window_start=email_start,
        ip_window_start=ip_start,
    )
    assert allowed.limited is False
    assert blocked.limited is True
    assert blocked.retry_after_seconds == retry_after_seconds(now, email_start, LOGIN_EMAIL_WINDOW)


def test_bucket_key_hides_the_ip_and_rotates_daily() -> None:
    day = datetime(2026, 10, 27, tzinfo=UTC).date()
    ip = "203.0.113.10"
    email = "visitor@example.com"
    key = bucket_key(purpose="login_ip", subject=ip, day=day, key="test-hmac-key")
    same = bucket_key(purpose="login_ip", subject=ip, day=day, key="test-hmac-key")
    other_day = bucket_key(
        purpose="login_ip",
        subject=ip,
        day=day + timedelta(days=1),
        key="test-hmac-key",
    )
    email_key = bucket_key(purpose="login_email", subject=email, day=day, key="test-hmac-key")
    assert key == same
    assert ip not in key
    assert email not in email_key
    assert key != other_day
    assert key != email_key


def test_missing_hmac_key_is_rejected() -> None:
    with pytest.raises(ValueError, match="hmac"):
        bucket_key(
            purpose="login_ip",
            subject="203.0.113.10",
            day=datetime(2026, 10, 27, tzinfo=UTC).date(),
            key="",
        )


def test_legal_acceptance_follows_the_current_version() -> None:
    assert needs_legal_acceptance(None) is True
    assert needs_legal_acceptance("2000-01-01.1") is True
    assert needs_legal_acceptance(LEGAL_DOCUMENT_VERSION) is False
