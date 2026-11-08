"""As regras puras do canal do titular e os prazos de retenção. FR-16, seções 10.4, 11.5 e 11.6.

Testa `app/domain/privacy.py` e `app/domain/retention.py` sem banco nem rede: o prazo de 15
dias corridos, a limpeza e a validação do pedido, o limite de 5 pedidos por IP por dia e o
período de cada regra da seção 11.6, com o corte estrito (o que está exatamente no corte não
venceu). `REGISTRATION_SESSIONS` tem período zero porque o corte é o próprio `expires_at` da
sessão, que já expira em 24 horas. As regras rodando no banco ficam em
`tests/integration/test_retention.py`.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.privacy import (
    PRIVACY_REQUEST_IP_LIMIT,
    RequestType,
    due_at,
    privacy_rate_decision,
    privacy_window_start,
    validate_request,
)
from app.domain.retention import RETENTION, RetentionRule, cutoff, is_expired

NOW = datetime(2026, 11, 3, 6, 0, tzinfo=UTC)


def test_request_is_due_in_fifteen_calendar_days() -> None:
    assert due_at(NOW) == datetime(2026, 11, 18, 6, 0, tzinfo=UTC)


def test_request_is_cleaned_and_normalized() -> None:
    draft, issues = validate_request(
        contact_email="  Ana@Example.COM ",
        request_type="deletion",
        description="  Quero apagar meus dados.  ",
    )
    assert issues == {}
    assert draft is not None
    assert draft.contact_email == "ana@example.com"
    assert draft.description == "Quero apagar meus dados."


def test_request_rejects_each_invalid_field() -> None:
    draft, issues = validate_request(
        contact_email="sem-arroba",
        request_type="marketing",
        description="   ",
    )
    assert draft is None
    assert set(issues) == {"contact_email", "request_type", "description"}
    _, too_long = validate_request(
        contact_email="ana@example.com",
        request_type=RequestType.OTHER.value,
        description="x" * 2001,
    )
    assert set(too_long) == {"description"}


def test_the_sixth_request_of_the_day_is_limited() -> None:
    window = privacy_window_start(NOW)
    assert window == datetime(2026, 11, 3, tzinfo=UTC)
    allowed = privacy_rate_decision(count=PRIVACY_REQUEST_IP_LIMIT, now=NOW, window_start=window)
    blocked = privacy_rate_decision(
        count=PRIVACY_REQUEST_IP_LIMIT + 1, now=NOW, window_start=window
    )
    assert not allowed.limited
    assert blocked.limited
    assert blocked.retry_after_seconds == 18 * 60 * 60


@pytest.mark.parametrize(
    ("rule", "period"),
    [
        (RetentionRule.INACTIVE_ACCOUNTS, timedelta(days=730)),
        (RetentionRule.MEMBER_CONVERSATIONS, timedelta(days=365)),
        (RetentionRule.GUEST_CONVERSATIONS, timedelta(days=30)),
        (RetentionRule.GUEST_KEYS, timedelta(days=30)),
        (RetentionRule.REGISTRATION_SESSIONS, timedelta(0)),
        (RetentionRule.AUTH_SESSIONS, timedelta(days=14)),
        (RetentionRule.RATE_LIMIT_WINDOWS, timedelta(hours=48)),
        (RetentionRule.AUDIT_EVENTS, timedelta(days=730)),
        (RetentionRule.PRIVACY_REQUESTS, timedelta(days=730)),
    ],
)
def test_each_rule_uses_the_period_of_section_11_6(rule: RetentionRule, period: timedelta) -> None:
    assert RETENTION[rule] == period
    assert cutoff(rule, NOW) == NOW - period
    assert is_expired(rule, NOW - period - timedelta(seconds=1), NOW)
    assert not is_expired(rule, NOW - period, NOW)


def test_every_rule_has_a_period() -> None:
    assert set(RETENTION) == set(RetentionRule)


def test_cutoff_needs_an_aware_clock() -> None:
    with pytest.raises(ValueError):
        cutoff(RetentionRule.AUDIT_EVENTS, datetime(2026, 11, 3))
