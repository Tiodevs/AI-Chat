"""Porta do rastro de IA. Seção 18.4 do SDD."""

from collections.abc import Sequence
from typing import Protocol

from app.domain.trace_policy import TraceEvent


class TraceRecorder(Protocol):
    def record_many(self, events: Sequence[TraceEvent]) -> None: ...


class NullTracer:
    def record_many(self, events: Sequence[TraceEvent]) -> None:
        return
