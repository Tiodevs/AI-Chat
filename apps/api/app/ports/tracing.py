"""Porta do rastro de IA. Seção 18.4 do SDD.

Camada de portas. `QaWorkflow`, `RegistrationWorkflow` e `IngestionService` mandam `TraceEvent`
já filtrados pela política de `app/domain/trace_policy.py`. O adaptador é `LangSmithTracer`
(`app/adapters/langsmith_tracing.py`), que usa um cliente do LangSmith por política. Sem
LangSmith configurado, a raiz de composição usa o `NullTracer` daqui.
"""

from collections.abc import Sequence
from typing import Protocol

from app.domain.trace_policy import TraceEvent


class TraceRecorder(Protocol):
    """Destino dos rastros de IA."""

    def record_many(self, events: Sequence[TraceEvent]) -> None:
        """Envia uma árvore de runs: o primeiro evento é a raiz, e os outros são filhos dela.

        É síncrono e não pode falhar para quem chama: o `LangSmithTracer` captura o erro e
        registra `tracing.failed` no log.
        """
        ...


class NullTracer:
    """Rastreador que descarta tudo. Testes e ambiente sem LangSmith."""

    def record_many(self, events: Sequence[TraceEvent]) -> None:
        """Não faz nada."""
        return
