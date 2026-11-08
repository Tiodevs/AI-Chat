"""Métricas Prometheus. Seção 18.3 do SDD.

Camada de núcleo. As métricas ficam num `CollectorRegistry` próprio, e o `GET /metrics`
(`app/controllers/metrics.py`) devolve só esse registro: as métricas padrão do processo, que
o `prometheus_client` põe no registro global, não saem. Quem observa cada métrica está no
comentário dela. Na exposição, o `prometheus_client` acrescenta `_total` aos contadores.

As séries de titular e de retenção vêm do banco, porque o `retention-job` roda em outro
processo, que a coleta não alcança. A cada coleta, `app/services/ops_metrics.py` lê o banco e
grava em `SNAPSHOT`, e o `DatabaseCollector` as expõe.

Os valores ficam na memória do processo: um deploy novo recomeça os contadores do zero, e o
Prometheus trata esse recomeço.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily, Metric

REGISTRY = CollectorRegistry()

# Pedidos e duração por rota, observados pelo `RequestIdMiddleware` no fim de cada pedido.
# `route` é o modelo do caminho; sem rota casada, `unmatched`.
HTTP_REQUESTS = Counter(
    "atrium_http_requests", "Pedidos HTTP", ["route", "method", "status"], registry=REGISTRY
)
HTTP_DURATION = Histogram(
    "atrium_http_request_duration_seconds", "Duração dos pedidos", ["route"], registry=REGISTRY
)
# Desfechos, primeiro token e maior similaridade das perguntas, observados por
# `app/workflows/qa.py`. Os baldes do primeiro token incluem 3 s, o limiar do alerta de
# latência da seção 18.3.
QA_OUTCOMES = Counter(
    "atrium_qa_outcomes", "Desfechos das perguntas", ["outcome"], registry=REGISTRY
)
QA_FIRST_TOKEN = Histogram(
    "atrium_qa_first_token_seconds",
    "Tempo até o primeiro token",
    buckets=(0.25, 0.5, 1, 1.5, 2, 3, 5, 10, 30),
    registry=REGISTRY,
)
# Similaridade de 0 a 1, em baldes de 0,1. Hoje só vê candidatos que passaram do piso; a
# Etapa 13.5 passa a medir a melhor similaridade antes do piso.
QA_TOP_SIMILARITY = Histogram(
    "atrium_qa_top_similarity",
    "Maior similaridade recuperada",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
    registry=REGISTRY,
)
# Tokens por modelo e `direction` (`input` ou `output`) e duração por `operation` (`rewrite`
# e `generate`), observados por `app/workflows/qa.py`.
LLM_TOKENS = Counter(
    "atrium_llm_tokens", "Tokens do modelo", ["model", "direction"], registry=REGISTRY
)
LLM_DURATION = Histogram(
    "atrium_llm_duration_seconds",
    "Duração das chamadas ao modelo",
    ["operation"],
    registry=REGISTRY,
)
# Fração do orçamento usada no dia. `app/services/budget.py` grava a cada conferência do teto.
LLM_BUDGET_RATIO = Gauge("atrium_llm_budget_ratio", "Uso do orçamento diário", registry=REGISTRY)
# 1 com o circuito do Gemini aberto, 0 fechado. Quem grava: `app/adapters/circuit_breaker.py`.
LLM_CIRCUIT_OPEN = Gauge("atrium_llm_circuit_open", "1 com o circuito aberto", registry=REGISTRY)
# Funil do cadastro por `event` e `path` (`chat` ou `form`), contado por
# `app/services/registration.py` e `app/workflows/registration.py`.
REGISTRATION_EVENTS = Counter(
    "atrium_registration_events", "Eventos de cadastro", ["event", "path"], registry=REGISTRY
)
# Versões ingeridas por `status`, contadas por `app/services/ingestion.py`.
INGESTION_VERSIONS = Counter(
    "atrium_ingestion_versions", "Versões de documento ingeridas", ["status"], registry=REGISTRY
)
# Notas do visitante (`helpful` ou `not_helpful`), contadas por `app/services/conversations.py`.
FEEDBACK = Counter("atrium_feedback", "Feedback do visitante", ["rating"], registry=REGISTRY)

# Os valores de `event` da seção 18.3. Nenhum módulo lê esta constante hoje.
REGISTRATION_EVENT_NAMES = frozenset(
    {"started", "extracted", "optional_skipped", "password_set", "completed", "abandoned"}
)


@dataclass(slots=True)
class DatabaseSnapshot:
    """Valores lidos do banco a cada coleta. O retention-job roda em outro processo.

    `loaded` fica falso até a primeira leitura que deu certo. Uma leitura que falha depois
    mantém os valores anteriores (seção 18.3).
    """

    dsr_open: int = 0
    dsr_overdue: int = 0
    retention_deleted: dict[str, int] = field(default_factory=dict)
    retention_last_run_seconds: float | None = None
    loaded: bool = False


# Um por processo: só `app/services/ops_metrics.py` escreve, e só `DatabaseCollector` lê.
SNAPSHOT = DatabaseSnapshot()


class DatabaseCollector:
    """Coletor das séries que vêm do banco: `atrium_dsr_open` e as duas de retenção."""

    def collect(self) -> Iterable[Metric]:
        """Gera as séries do `SNAPSHOT`. O registro chama este método a cada exposição.

        Antes da primeira leitura, não gera nada: as séries ficam ausentes, em vez de zeradas,
        e o alerta de retenção parada da seção 18.3 dispara também sem a série.
        """
        if not SNAPSHOT.loaded:
            return
        dsr = GaugeMetricFamily("atrium_dsr_open", "Pedidos de titular abertos", labels=["overdue"])
        dsr.add_metric(["false"], SNAPSHOT.dsr_open)
        dsr.add_metric(["true"], SNAPSHOT.dsr_overdue)
        yield dsr
        deleted = CounterMetricFamily(
            "atrium_retention_deleted", "Registros eliminados pela retenção", labels=["rule"]
        )
        for rule, total in sorted(SNAPSHOT.retention_deleted.items()):
            deleted.add_metric([rule], total)
        yield deleted
        if SNAPSHOT.retention_last_run_seconds is not None:
            yield GaugeMetricFamily(
                "atrium_retention_last_run_timestamp_seconds",
                "Instante da última execução do retention-job",
                value=SNAPSHOT.retention_last_run_seconds,
            )


REGISTRY.register(DatabaseCollector())


def render_metrics() -> bytes:
    """O registro da API no formato de texto do Prometheus, com as séries do `SNAPSHOT`."""
    return generate_latest(REGISTRY)
