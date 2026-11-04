"""Métricas Prometheus. Seção 18.3 do SDD."""

from collections.abc import Iterable
from dataclasses import dataclass, field

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily, Metric

REGISTRY = CollectorRegistry()

HTTP_REQUESTS = Counter(
    "atrium_http_requests", "Pedidos HTTP", ["route", "method", "status"], registry=REGISTRY
)
HTTP_DURATION = Histogram(
    "atrium_http_request_duration_seconds", "Duração dos pedidos", ["route"], registry=REGISTRY
)
QA_OUTCOMES = Counter(
    "atrium_qa_outcomes", "Desfechos das perguntas", ["outcome"], registry=REGISTRY
)
QA_FIRST_TOKEN = Histogram(
    "atrium_qa_first_token_seconds",
    "Tempo até o primeiro token",
    buckets=(0.25, 0.5, 1, 1.5, 2, 3, 5, 10, 30),
    registry=REGISTRY,
)
QA_TOP_SIMILARITY = Histogram(
    "atrium_qa_top_similarity",
    "Maior similaridade recuperada",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
    registry=REGISTRY,
)
LLM_TOKENS = Counter(
    "atrium_llm_tokens", "Tokens do modelo", ["model", "direction"], registry=REGISTRY
)
LLM_DURATION = Histogram(
    "atrium_llm_duration_seconds",
    "Duração das chamadas ao modelo",
    ["operation"],
    registry=REGISTRY,
)
LLM_BUDGET_RATIO = Gauge("atrium_llm_budget_ratio", "Uso do orçamento diário", registry=REGISTRY)
LLM_CIRCUIT_OPEN = Gauge("atrium_llm_circuit_open", "1 com o circuito aberto", registry=REGISTRY)
REGISTRATION_EVENTS = Counter(
    "atrium_registration_events", "Eventos de cadastro", ["event", "path"], registry=REGISTRY
)
INGESTION_VERSIONS = Counter(
    "atrium_ingestion_versions", "Versões de documento ingeridas", ["status"], registry=REGISTRY
)
FEEDBACK = Counter("atrium_feedback", "Feedback do visitante", ["rating"], registry=REGISTRY)

REGISTRATION_EVENT_NAMES = frozenset(
    {"started", "extracted", "optional_skipped", "password_set", "completed", "abandoned"}
)


@dataclass(slots=True)
class DatabaseSnapshot:
    """Valores lidos do banco a cada coleta. O retention-job roda em outro processo."""

    dsr_open: int = 0
    dsr_overdue: int = 0
    retention_deleted: dict[str, int] = field(default_factory=dict)
    retention_last_run_seconds: float | None = None
    loaded: bool = False


SNAPSHOT = DatabaseSnapshot()


class DatabaseCollector:
    def collect(self) -> Iterable[Metric]:
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
    return generate_latest(REGISTRY)
