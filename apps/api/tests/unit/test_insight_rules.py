"""As regras puras da visão geral e da qualidade do admin. FR-15, seções 11.8, 12 e 15.5.

Testa `app/domain/insights.py`, da Etapa 7.2, sem banco nem rede: os períodos de 7 ou 30
dias, a janela anterior de mesmo tamanho, as taxas nulas sem denominador, a intenção derivada
do desfecho, o motivo da revelação de identidade, o link do rastro pelo
`LANGSMITH_RUN_URL_TEMPLATE`, o pseudônimo de 8 caracteres e a razão do orçamento. As rotas
ficam em `tests/integration/test_admin_insights.py`.
"""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from app.domain.insights import (
    Intent,
    abstentions,
    budget_ratio,
    clean_reason,
    days_of,
    intent_counts,
    rate,
    short_pseudonym,
    trace_url,
    valid_period,
    windows_for,
)

NOW = datetime(2031, 1, 15, 12, 0, tzinfo=UTC)
RUN = UUID("00000000-0000-4000-8000-000000000042")


def test_only_seven_or_thirty_days_are_periods() -> None:
    assert valid_period(7)
    assert valid_period(30)
    assert not valid_period(14)


def test_the_previous_window_has_the_same_size_right_before() -> None:
    windows = windows_for(NOW, 7)
    assert windows.current.end == NOW
    assert windows.current.start == NOW - timedelta(days=7)
    assert windows.previous.end == windows.current.start
    assert windows.previous.start == NOW - timedelta(days=14)
    days = days_of(windows.current)
    assert days[0] == date(2031, 1, 8)
    assert days[-1] == date(2031, 1, 15)


def test_rates_are_none_without_a_denominator() -> None:
    assert rate(1, 4) == 0.25
    assert rate(0, 0) is None


def test_intent_comes_from_the_outcome() -> None:
    counts = intent_counts({"answered": 3, "refused": 2, "off_topic": 1, "abstained": 4})
    assert counts == {
        Intent.PUBLIC_INFO.value: 7,
        Intent.MEDICAL_ADVICE.value: 2,
        Intent.OFF_TOPIC.value: 1,
    }


def test_abstention_counts_abstained_and_grounding_failed() -> None:
    assert abstentions({"abstained": 2, "grounding_failed": 1, "answered": 5}) == 3


def test_reveal_needs_a_real_reason() -> None:
    assert clean_reason("curto") is None
    assert clean_reason("  Pedido   de titular  nº 12 ") == "Pedido de titular nº 12"
    assert clean_reason("x" * 501) is None


def test_trace_link_needs_a_template_with_the_run_id() -> None:
    template = "https://smith.example/o/w/projects/p/p1/r/{run_id}"
    assert trace_url(template, RUN) == f"https://smith.example/o/w/projects/p/p1/r/{RUN}"
    assert trace_url("", RUN) is None
    assert trace_url(template, None) is None


def test_pseudonym_and_budget_helpers() -> None:
    assert short_pseudonym("abcdef0123456789") == "abcdef01"
    assert budget_ratio(800, 1000) == 0.8
    assert budget_ratio(10, 0) == 0.0
