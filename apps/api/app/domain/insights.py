"""Regras da visão geral e da qualidade do admin. Seções 11.8, 12 e 15.5 do SDD.

Camada de domínio. `InsightsService` (`app/services/insights.py`) usa os períodos, as taxas, o
pseudônimo curto, o motivo da revelação e o link do rastro; `InsightsRepository` usa a janela,
o funil, o filtro de feedback e o tamanho da página do inspetor; `admin_insights.py`, nos
controladores, usa o período padrão.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from uuid import UUID

from app.domain.outcomes import Outcome

# Períodos aceitos em `?period_days=` (seção 12). Sem o parâmetro, vale 7.
PERIOD_DAYS = (7, 30)
DEFAULT_PERIOD_DAYS = 7
# O inspetor mostra 8 caracteres do HMAC de `PSEUDONYM_KEY`, nunca nome nem e-mail (seção 12).
PSEUDONYM_CHARS = 8
# Motivo da revelação de identidade: de 10 a 500 caracteres depois de juntar os espaços.
REVEAL_REASON_MIN_CHARS = 10
REVEAL_REASON_MAX_CHARS = 500
# O inspetor lista até 50 conversas.
CONVERSATION_PAGE = 50
# Marcador que `LANGSMITH_RUN_URL_TEMPLATE` tem no lugar do id do run (seção 17).
RUN_ID_PLACEHOLDER = "{run_id}"


class InsightAction(StrEnum):
    """Ações do admin gravadas em `audit_events` (seção 3.2).

    Abrir uma conversa no inspetor grava `conversation.view`. Revelar quem a fez grava
    `identity.reveal`, com o motivo (seção 11.8).
    """

    CONVERSATION_VIEW = "conversation.view"
    IDENTITY_REVEAL = "identity.reveal"


class Intent(StrEnum):
    """Intenção derivada do desfecho gravado. A mensagem não guarda a intenção.

    Regra da seção 15.5: `refused` é orientação médica, `off_topic` é fora do tema, e o resto,
    inclusive `degraded`, `error` e `cancelled`, conta como informação pública. O valor
    `off_topic` daqui corresponde ao `other` do classificador e também cobre a pergunta de
    confiança baixa.
    """

    PUBLIC_INFO = "public_info"
    MEDICAL_ADVICE = "medical_advice"
    OFF_TOPIC = "off_topic"


class FeedbackFilter(StrEnum):
    """Filtro de feedback do inspetor de qualidade (seção 12). `none` é resposta sem nota."""

    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"
    NONE = "none"


class FunnelStep(StrEnum):
    """Etapas do funil de cadastro da visão geral, contadas por caminho (seção 12)."""

    STARTED = "started"
    PASSWORD_SET = "password_set"
    COMPLETED = "completed"


# A taxa de abstenção soma `abstained` e `grounding_failed` (seções 15.5 e 18.3).
ABSTENTION_OUTCOMES = frozenset({Outcome.ABSTAINED.value, Outcome.GROUNDING_FAILED.value})


@dataclass(frozen=True, slots=True)
class Window:
    """Intervalo de uma consulta. O repositório inclui `start` e exclui `end`."""

    start: datetime
    end: datetime


@dataclass(frozen=True, slots=True)
class Windows:
    """O período atual e o anterior, de mesmo tamanho, para comparar os indicadores."""

    current: Window
    previous: Window


def valid_period(days: int) -> bool:
    """Só 7 ou 30 dias. Outro valor vira 422 com `PERIOD_INVALID`."""
    return days in PERIOD_DAYS


def windows_for(now: datetime, days: int) -> Windows:
    """Período atual termina agora. O anterior tem o mesmo tamanho, logo antes."""
    size = timedelta(days=days)
    start = now - size
    return Windows(current=Window(start, now), previous=Window(start - size, start))


def days_of(window: Window) -> list[date]:
    """Dias UTC que o período toca, do mais antigo ao mais novo.

    Um período de 7 dias que não começa à meia-noite toca 8 datas. A tendência diária da visão
    geral tem um ponto por data, com zero nos dias sem pergunta.
    """
    first = window.start.date()
    last = window.end.date()
    return [first + timedelta(days=offset) for offset in range((last - first).days + 1)]


def rate(numerator: int, denominator: int) -> float | None:
    """Razão, ou `None` sem denominador. A API devolve `null` nesse caso (seção 12)."""
    if denominator <= 0:
        return None
    return numerator / denominator


def intent_for(outcome: str) -> Intent:
    """Intenção de um desfecho, pela regra de `Intent`."""
    if outcome == Outcome.REFUSED.value:
        return Intent.MEDICAL_ADVICE
    if outcome == Outcome.OFF_TOPIC.value:
        return Intent.OFF_TOPIC
    return Intent.PUBLIC_INFO


def intent_counts(outcomes: dict[str, int]) -> dict[str, int]:
    """Converte contagens por desfecho em contagens por intenção. Toda intenção aparece."""
    totals = {item.value: 0 for item in Intent}
    for outcome, count in outcomes.items():
        totals[intent_for(outcome).value] += count
    return totals


def abstentions(outcomes: dict[str, int]) -> int:
    """Quantas respostas foram abstenção ou falha de fundamentação."""
    return sum(count for outcome, count in outcomes.items() if outcome in ABSTENTION_OUTCOMES)


def short_pseudonym(full: str) -> str:
    """Os 8 primeiros caracteres do pseudônimo HMAC, para o `PseudonymBadge`."""
    return full[:PSEUDONYM_CHARS]


def clean_reason(reason: str) -> str | None:
    """Motivo da revelação com os espaços juntados, ou `None` fora de 10 a 500 caracteres.

    O motivo limpo vai para a auditoria `identity.reveal`. Com `None`, o serviço responde 422
    em `field_errors.reason`.
    """
    value = " ".join(reason.split())
    if not REVEAL_REASON_MIN_CHARS <= len(value) <= REVEAL_REASON_MAX_CHARS:
        return None
    return value


def trace_url(template: str, run_id: UUID | None) -> str | None:
    """Link do rastro no LangSmith. Sem modelo configurado, o inspetor mostra só o id.

    Sem `run_id`, ou com um modelo sem `{run_id}`, devolve `None`.
    """
    if run_id is None or RUN_ID_PLACEHOLDER not in template:
        return None
    return template.replace(RUN_ID_PLACEHOLDER, str(run_id))


def budget_ratio(used: int, budget: int) -> float:
    """Uso do dia sobre o teto, para o card de orçamento. Com o teto desligado, vale 0."""
    if budget <= 0:
        return 0.0
    return used / budget
