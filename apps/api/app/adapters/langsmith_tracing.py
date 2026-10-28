"""Cliente do LangSmith, políticas e o flush do desligamento. Seção 18.4."""

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

_runtime: "LangSmithRuntime | None" = None
_cache_key: tuple[object, ...] | None = None


class _Flushable(Protocol):
    def flush(self) -> None: ...


@dataclass(frozen=True, slots=True)
class PolicyClients:
    full: Client
    masked: Client
    metadata_only: Client

    def client_for(self, policy: TracePolicy) -> Client:
        if policy == "full":
            return self.full
        if policy == "masked":
            return self.masked
        return self.metadata_only

    def all(self) -> tuple[Client, Client, Client]:
        return (self.full, self.masked, self.metadata_only)

    def close(self) -> None:
        for client in self.all():
            try:
                client.close()
            except Exception as exc:
                _warn("tracing.close_failed", exc)


class LangSmithTracer:
    def __init__(self, clients: PolicyClients, project: str) -> None:
        self._clients = clients
        self._project = project

    def record_many(self, events: Sequence[TraceEvent]) -> None:
        if not events:
            return
        try:
            self._post(events)
        except Exception as exc:
            _warn("tracing.failed", exc)

    def _post(self, events: Sequence[TraceEvent]) -> None:
        root = events[0]
        client = self._clients.client_for(root.policy)
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
            root_run.end(outputs=_plain(root.outputs))


class LangSmithFeedbackSink:
    def __init__(self, client: Client) -> None:
        self._client = client

    async def record(self, run_id: UUID, key: str, score: float) -> None:
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
    """Três clientes. O hide global não é usado: ele desliga o anonimizador."""
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
    global _runtime, _cache_key
    if _runtime is not None:
        _runtime.clients.close()
    _runtime = None
    _cache_key = None


def langsmith_api_url(endpoint: str) -> str:
    return endpoint or US_ENDPOINT


def wait_for_all_tracers() -> None:
    """Espera os rastros pendentes. O lifespan chama isto no desligamento."""
    clients: Sequence[_Flushable] = () if _runtime is None else _runtime.clients.all()
    flush_clients(clients)
    _flush_langchain()


def flush_clients(clients: Sequence[_Flushable]) -> None:
    for client in clients:
        try:
            client.flush()
        except Exception as exc:
            _warn("tracing.flush_failed", exc)


def feedback_sink_for(settings: Settings) -> FeedbackSink:
    from app.adapters.noop_feedback import NoopFeedbackSink

    runtime = runtime_for(settings)
    if runtime is None:
        return NoopFeedbackSink()
    return runtime.feedback


def tracer_for(settings: Settings) -> LangSmithTracer | None:
    runtime = runtime_for(settings)
    if runtime is None:
        return None
    return runtime.tracer


def _hide_masked(payload: dict[str, Any]) -> dict[str, Any]:
    return outgoing("masked", payload)


def _plain(payload: dict[str, object]) -> dict[str, Any]:
    return dict(payload)


def _flush_langchain() -> None:
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
    structlog.get_logger("atrium").warning(event, error_type=type(exc).__name__)
