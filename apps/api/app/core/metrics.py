"""Métricas Prometheus. Seção 18.3 do SDD."""

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

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
DSR_OPEN = Gauge("atrium_dsr_open", "Pedidos de titular abertos", ["overdue"], registry=REGISTRY)
RETENTION_DELETED = Counter(
    "atrium_retention_deleted", "Registros eliminados", ["rule"], registry=REGISTRY
)

REGISTRATION_EVENT_NAMES = frozenset(
    {"started", "extracted", "optional_skipped", "password_set", "completed", "abandoned"}
)


def render_metrics() -> bytes:
    return generate_latest(REGISTRY)
