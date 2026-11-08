"""Cliente do LangSmith, políticas e o flush do desligamento. Seção 18.4.

Adaptador das portas `TraceRecorder` (`app.ports.tracing`) e `FeedbackSink`
(`app.ports.feedback`). O domínio (`app.domain.trace_policy`) decide o que cada passo pode
mostrar e monta os eventos; este arquivo os escreve no LangSmith com três clientes, um por
política, que aplicam a projeção de novo antes do envio (ADR-006). A chamada ao modelo corre
com o rastro automático desligado (`tracing_scope`), então o LangSmith só recebe estes rastros
explícitos.

Quem usa: `app.core.container` (`tracer_for` e `feedback_sink_for`), o `lifespan` de
`app.main` (`wait_for_all_tracers`), o script `seed` (`tracer_for`) e os scripts de avaliação
(`langsmith_api_url`). O runtime vive uma vez por processo, guardado neste módulo.

Os runs são escritos depois de o pipeline terminar, então a duração que o LangSmith mostra
para eles é a da escrita, não a da pergunta. O tempo real fica nos spans do OpenTelemetry e no
`latency_ms` da mensagem.
"""

import importlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

import structlog
from langsmith import Client, trace, tracing_context

from app.core.config import Settings
from app.domain.trace_policy import (
    TraceEvent,
    TracePolicy,
    anonymize_payload,
    outgoing,
)
from app.ports.feedback import FeedbackSink

# Região dos Estados Unidos, decisão D-2. Vazio na configuração usa este endpoint.
US_ENDPOINT = "https://api.smith.langchain.com"

# O runtime do processo e a configuração que o gerou. Uma configuração nova, como nos
# testes, fecha os clientes antigos e monta outros.
_runtime: "LangSmithRuntime | None" = None
_cache_key: tuple[object, ...] | None = None


class _Flushable(Protocol):
    """O que `flush_clients` precisa de um cliente: só o `flush`."""

    def flush(self) -> None: ...


@dataclass(frozen=True, slots=True)
class PolicyClients:
    """Os três clientes do LangSmith, um por política de rastro da seção 18.4."""

    full: Client
    masked: Client
    metadata_only: Client

    def client_for(self, policy: TracePolicy) -> Client:
        """O cliente da política. Uma política desconhecida cai no mais restrito."""
        if policy == "full":
            return self.full
        if policy == "masked":
            return self.masked
        return self.metadata_only

    def all(self) -> tuple[Client, Client, Client]:
        """Os três clientes, para fechar ou descarregar todos."""
        return (self.full, self.masked, self.metadata_only)

    def close(self) -> None:
        """Fecha os três. Uma falha vai ao log `tracing.close_failed` e não interrompe os outros."""
        for client in self.all():
            try:
                client.close()
            except Exception as exc:
                _warn("tracing.close_failed", exc)


class LangSmithTracer:
    """Implementa `TraceRecorder`: escreve no LangSmith os eventos que o domínio montou.

    O primeiro evento é a raiz (`qa`, `registration` ou `ingestion`) e os seguintes viram
    filhos dela, como o `qa.rewrite`. Cada run sai pelo cliente da própria política.
    """

    def __init__(self, clients: PolicyClients, project: str) -> None:
        self._clients = clients
        self._project = project

    def record_many(self, events: Sequence[TraceEvent]) -> None:
        """Escreve a árvore de runs. Uma falha vai ao log `tracing.failed` e não sobe.

        Assim o rastro nunca derruba a resposta ao visitante. O log leva só o tipo da
        exceção.
        """
        if not events:
            return
        try:
            self._post(events)
        except Exception as exc:
            _warn("tracing.failed", exc)

    def _post(self, events: Sequence[TraceEvent]) -> None:
        """Cria a raiz e os filhos com `trace`, do SDK do LangSmith.

        1. `tracing_context(enabled=True, ...)` liga o rastro só neste bloco, com o cliente,
           o projeto, as tags e os metadados da raiz. O `trace` só envia com o rastro ligado
           no contexto ou em `os.environ`, e a `Settings` pode ter lido `LANGSMITH_TRACING`
           do `.env`, que não vai para `os.environ`.
        2. `trace(...)` abre um run (um nó da árvore de rastro) com o `run_id` do evento. Na
           raiz da pergunta, ele é o id da mensagem do assistente, que liga o feedback do
           visitante ao rastro (seção 18.4).
        3. Cada filho abre com `parent=root_run` e fecha com as próprias saídas.
        4. A raiz fecha por último, com as saídas dela.

        Com `auto_batch_tracing`, o cliente põe os runs numa fila e os envia em lote por uma
        thread de fundo, então esta chamada não espera a rede.
        """
        root = events[0]
        client = self._clients.client_for(root.policy)
        # 1. e 2.
        with (
            tracing_context(
                enabled=True,
                client=client,
                project_name=self._project,
                tags=list(root.tags),
                metadata=_plain(root.metadata),
            ),
            trace(
                root.name,
                run_type="chain",
                inputs=_plain(root.inputs),
                project_name=self._project,
                tags=list(root.tags),
                metadata=_plain(root.metadata),
                client=client,
                run_id=root.run_id,
            ) as root_run,
        ):
            # 3.
            for child in events[1:]:
                child_client = self._clients.client_for(child.policy)
                with trace(
                    child.name,
                    run_type="chain",
                    inputs=_plain(child.inputs),
                    project_name=self._project,
                    parent=root_run,
                    tags=list(child.tags),
                    metadata=_plain(child.metadata),
                    client=child_client,
                    run_id=child.run_id,
                ) as child_run:
                    child_run.end(outputs=_plain(child.outputs))
            # 4.
            root_run.end(outputs=_plain(root.outputs))


class LangSmithFeedbackSink:
    """Implementa `FeedbackSink`: envia ao LangSmith a nota do visitante (seção 18.4)."""

    def __init__(self, client: Client) -> None:
        self._client = client

    async def record(self, run_id: UUID, key: str, score: float) -> None:
        """Cria o feedback `key` com `score` no run `run_id`.

        O `create_feedback` do SDK é um pedido HTTP bloqueante, então roda numa thread com
        `asyncio.to_thread`. O run raiz de uma pergunta é a raiz do próprio rastro, por isso
        `trace_id` recebe o mesmo id. Quem chama trata a falha (`send_user_feedback`).
        """
        import asyncio

        await asyncio.to_thread(
            self._client.create_feedback,
            run_id,
            key,
            score=score,
            trace_id=run_id,
        )


@dataclass(frozen=True, slots=True)
class LangSmithRuntime:
    """Os clientes, o tracer e o coletor de feedback de um processo."""

    clients: PolicyClients
    tracer: LangSmithTracer
    feedback: FeedbackSink


def build_policy_clients(
    *,
    api_key: str,
    api_url: str,
    sampling_rate: float,
    workspace_id: str | None = None,
    auto_batch_tracing: bool = True,
) -> PolicyClients:
    """Três clientes. O hide global não é usado: ele desliga o anonimizador.

    No SDK, `hide_inputs=True` manda entradas vazias; um `anonymizer` configurado passa na
    frente de um `hide_inputs` em função, que então nunca roda. Por isso:

    - `full`: o anonimizador troca e-mail, telefone e dígitos longos em entradas, saídas e
      metadados (seção 18.4).
    - `masked`: sem anonimizador, com `hide_inputs` e `hide_outputs` em função, que guardam só
      as chaves da política e anonimizam (`outgoing("masked", ...)`).
    - `metadata_only`: entradas e saídas sempre vazias, e o anonimizador nos metadados.

    Como os três passam `hide_inputs` e `hide_outputs` explícitos, as variáveis
    `LANGSMITH_HIDE_INPUTS` e `LANGSMITH_HIDE_OUTPUTS` do ambiente não valem para eles.
    `workspace_id` é preciso com uma chave de organização (seção 17). O teste das políticas
    passa `auto_batch_tracing=False`.
    """
    shared: dict[str, Any] = {
        "api_key": api_key,
        "api_url": api_url,
        "tracing_sampling_rate": sampling_rate,
        "auto_batch_tracing": auto_batch_tracing,
        "workspace_id": workspace_id,
    }
    return PolicyClients(
        full=Client(
            **shared,
            anonymizer=anonymize_payload,
            hide_inputs=False,
            hide_outputs=False,
        ),
        masked=Client(
            **shared,
            hide_inputs=_hide_masked,
            hide_outputs=_hide_masked,
        ),
        metadata_only=Client(
            **shared,
            anonymizer=anonymize_payload,
            hide_inputs=True,
            hide_outputs=True,
        ),
    )


def runtime_for(settings: Settings) -> LangSmithRuntime | None:
    """O runtime do LangSmith para a configuração, ou `None` com o rastro desligado.

    Fica em cache enquanto as variáveis do LangSmith não mudam. Sem `LANGSMITH_TRACING` ligado
    ou sem chave, não há runtime, e quem chama usa o `NullTracer` e o `NoopFeedbackSink`.
    """
    global _runtime, _cache_key
    key = (
        settings.langsmith_tracing,
        settings.langsmith_api_key,
        settings.langsmith_project,
        settings.langsmith_endpoint,
        settings.langsmith_workspace_id,
        settings.langsmith_tracing_sampling_rate,
    )
    if _cache_key == key:
        return _runtime
    reset_langsmith_runtime()
    _cache_key = key
    if not settings.langsmith_tracing or not settings.langsmith_api_key:
        _runtime = None
        return None
    clients = build_policy_clients(
        api_key=settings.langsmith_api_key,
        api_url=langsmith_api_url(settings.langsmith_endpoint),
        sampling_rate=settings.langsmith_tracing_sampling_rate,
        workspace_id=settings.langsmith_workspace_id or None,
    )
    _runtime = LangSmithRuntime(
        clients=clients,
        tracer=LangSmithTracer(clients, settings.langsmith_project),
        feedback=LangSmithFeedbackSink(clients.full),
    )
    return _runtime


def reset_langsmith_runtime() -> None:
    """Fecha os clientes e esquece o runtime.

    `runtime_for` chama isto quando a configuração muda, e o `conftest.py` dos testes, antes e
    depois de cada teste.
    """
    global _runtime, _cache_key
    if _runtime is not None:
        _runtime.clients.close()
    _runtime = None
    _cache_key = None


def langsmith_api_url(endpoint: str) -> str:
    """O endpoint configurado, ou o dos Estados Unidos quando vazio (decisão D-2)."""
    return endpoint or US_ENDPOINT


def wait_for_all_tracers() -> None:
    """Espera os rastros pendentes. O lifespan chama isto no desligamento.

    Descarrega a fila dos três clientes e a dos tracers globais do LangChain, para um deploy
    não perder rastros (seção 18.4, "Encerramento").
    """
    clients: Sequence[_Flushable] = () if _runtime is None else _runtime.clients.all()
    flush_clients(clients)
    _flush_langchain()


def flush_clients(clients: Sequence[_Flushable]) -> None:
    """Chama `flush` em cada cliente. Uma falha vai ao log e não impede os outros."""
    for client in clients:
        try:
            client.flush()
        except Exception as exc:
            _warn("tracing.flush_failed", exc)


def feedback_sink_for(settings: Settings) -> FeedbackSink:
    """O coletor de feedback do LangSmith, ou o `NoopFeedbackSink` com o rastro desligado."""
    from app.adapters.noop_feedback import NoopFeedbackSink

    runtime = runtime_for(settings)
    if runtime is None:
        return NoopFeedbackSink()
    return runtime.feedback


def tracer_for(settings: Settings) -> LangSmithTracer | None:
    """O tracer do LangSmith, ou `None` com o rastro desligado; quem chama usa o `NullTracer`."""
    runtime = runtime_for(settings)
    if runtime is None:
        return None
    return runtime.tracer


def _hide_masked(payload: dict[str, Any]) -> dict[str, Any]:
    """O `hide_inputs` e o `hide_outputs` do cliente `masked`: a projeção do domínio."""
    return outgoing("masked", payload)


def _plain(payload: dict[str, object]) -> dict[str, Any]:
    """Uma cópia rasa no tipo `dict[str, Any]` que o SDK pede."""
    return dict(payload)


def _flush_langchain() -> None:
    """Descarrega os tracers globais do LangChain, se o módulo e a função existirem.

    O import por nome evita depender do LangChain no import deste arquivo.
    """
    try:
        module = importlib.import_module("langchain_core.tracers.langchain")
    except ImportError:
        return
    flush = getattr(module, "wait_for_all_tracers", None)
    if not callable(flush):
        return
    try:
        flush()
    except Exception as exc:
        _warn("tracing.flush_failed", exc)


def _warn(event: str, exc: BaseException) -> None:
    """Log de aviso só com o tipo da exceção, porque a mensagem pode trazer conteúdo (NFR-7)."""
    structlog.get_logger("atrium").warning(event, error_type=type(exc).__name__)
