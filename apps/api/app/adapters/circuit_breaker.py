"""Circuito do chat: 5 falhas seguidas, aberto por 60 segundos. Seção 7.1 do SDD."""

from datetime import datetime, timedelta

from app.ports.clock import Clock

FAILURE_LIMIT = 5
OPEN_SECONDS = 60.0


class CircuitBreaker:
    def __init__(
        self,
        clock: Clock,
        *,
        failure_limit: int = FAILURE_LIMIT,
        open_seconds: float = OPEN_SECONDS,
    ) -> None:
        self._clock = clock
        self._failure_limit = failure_limit
        self._open_seconds = open_seconds
        self._consecutive_failures = 0
        self._open_until: datetime | None = None

    def allow(self) -> bool:
        if self._open_until is None:
            return True
        if self._clock.now() >= self._open_until:
            self._open_until = None
            return True
        return False

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._open_until = None

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._failure_limit:
            self._open_until = self._clock.now() + timedelta(seconds=self._open_seconds)
