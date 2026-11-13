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

# Atendimento humano (seção 29.12). Pedidos por `trigger` e encerramentos por `close_reason`,
# contados por `services/handoff.py`, `services/attendance.py` e `services/handoff_sweep.py`.
HANDOFF_REQUESTS = Counter(
    "atrium_handoff_requests", "Pedidos de atendimento", ["trigger"], registry=REGISTRY
)
HANDOFF_CLOSED = Counter(
    "atrium_handoff_closed", "Atendimentos encerrados", ["close_reason"], registry=REGISTRY
)
# Espera na fila até alguém assumir, observada por `services/attendance.py`.
HANDOFF_WAIT = Histogram(
    "atrium_handoff_wait_seconds",
    "Espera na fila até assumir",
    buckets=(5, 15, 30, 60, 120, 300, 600, 900),
    registry=REGISTRY,
)
# Mensagens por `role` (`user` ou `attendant`) e identificadores removidos por `kind`.
HANDOFF_MESSAGES = Counter(
    "atrium_handoff_messages", "Mensagens do atendimento", ["role"], registry=REGISTRY
)
HANDOFF_REDACTIONS = Counter(
    "atrium_handoff_redactions", "Identificadores removidos", ["kind"], registry=REGISTRY
)
# Fluxos SSE abertos por `stream` (`ask`, `handoff` ou `attendance`), neste processo.
SSE_STREAMS = Gauge("atrium_sse_streams", "Fluxos SSE abertos", ["stream"], registry=REGISTRY)
# 1 com a conexão do `LISTEN` aberta, 0 fora do ar. Quem grava: `app/adapters/realtime.py`.
REALTIME_LISTENER_UP = Gauge(
    "atrium_realtime_listener_up", "1 com o ouvinte do LISTEN conectado", registry=REGISTRY
)

# Canal WhatsApp (seção 30.12). Contados por `services/whatsapp_webhook.py` e
# `services/whatsapp.py`, sem texto, sem BSUID e sem telefone nos rótulos.
WHATSAPP_EVENTS = Counter(
    "atrium_whatsapp_events",
    "Eventos do webhook do WhatsApp",
    ["kind", "message_type"],
    registry=REGISTRY,
)
WHATSAPP_SIGNATURE_FAILURES = Counter(
    "atrium_whatsapp_signature_failures", "Webhooks com assinatura inválida", registry=REGISTRY
)
WHATSAPP_PROCESSING_LAG = Histogram(
    "atrium_whatsapp_processing_lag_seconds",
    "Do recebimento do webhook ao fim do processamento",
    buckets=(1, 2, 5, 10, 15, 30, 60, 120),
    registry=REGISTRY,
)
WHATSAPP_OUTBOUND = Counter(
    "atrium_whatsapp_outbound", "Mensagens de saída", ["kind", "status"], registry=REGISTRY
)
WHATSAPP_SEND_ERRORS = Counter(
    "atrium_whatsapp_send_errors",
    "Falhas de envio pela Graph API",
    ["error_code"],
    registry=REGISTRY,
)

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
    # A fila e a equipe presente vêm do banco para valerem com mais de uma réplica (29.12).
    handoff_queue: int = 0
    handoff_attendants_available: int = 0
    # O canal WhatsApp (seção 30.12): pendentes por direção, a idade do mais antigo e as
    # mensagens de serviço enviadas no mês.
    whatsapp_pending: dict[str, int] = field(default_factory=dict)
    whatsapp_oldest_seconds: dict[str, float] = field(default_factory=dict)
    whatsapp_service_messages_month: int = 0
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
        yield GaugeMetricFamily(
            "atrium_handoff_queue", "Atendimentos na fila", value=SNAPSHOT.handoff_queue
        )
        yield GaugeMetricFamily(
            "atrium_handoff_attendants_available",
            "Pessoas da equipe presentes",
            value=SNAPSHOT.handoff_attendants_available,
        )
        pending = GaugeMetricFamily(
            "atrium_whatsapp_pending", "Eventos e mensagens pendentes", labels=["direction"]
        )
        oldest = GaugeMetricFamily(
            "atrium_whatsapp_oldest_pending_seconds",
            "Idade do pendente mais antigo",
            labels=["direction"],
        )
        for direction in ("inbound", "outbound"):
            pending.add_metric([direction], SNAPSHOT.whatsapp_pending.get(direction, 0))
            oldest.add_metric([direction], SNAPSHOT.whatsapp_oldest_seconds.get(direction, 0.0))
        yield pending
        yield oldest
        yield GaugeMetricFamily(
            "atrium_whatsapp_service_messages_month",
            "Mensagens de serviço enviadas no mês",
            value=SNAPSHOT.whatsapp_service_messages_month,
        )
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
