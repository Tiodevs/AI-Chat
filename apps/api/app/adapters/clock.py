"""Relógio do sistema, em UTC. Implementa a porta `Clock` (`app.ports.clock`).

Adaptador de infraestrutura (seção 6.2): o domínio não lê o relógio do sistema, e os serviços
recebem um `Clock` para os testes controlarem o tempo. Quem usa: `app.core.container`
(`get_clock`), o `lifespan` de `app.main`, o `GeminiChatProvider` (pelo circuit breaker) e os
scripts.
"""

from datetime import UTC, datetime


class SystemClock:
    """O relógio de verdade. Os timestamps do banco são `timestamptz` em UTC (seção 8)."""

    def now(self) -> datetime:
        """O instante atual com fuso UTC, nunca um `datetime` sem fuso."""
        return datetime.now(UTC)
