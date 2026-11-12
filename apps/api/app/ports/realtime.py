"""Porta do aviso entre processos do atendimento humano. Seção 29.6 e ADR-016 do SDD.

Camada de portas. Os fluxos SSE do visitante e do console (`services/handoff.py` e
`services/attendance.py`) assinam o broker e acordam a cada aviso; os serviços que gravam
chamam `committed` depois do commit. Os adaptadores, em `app/adapters/realtime.py`, são o
`PostgresNotifyBroker`, que ouve o `LISTEN atrium_handoff` numa conexão fora do pool, e o
`InMemoryBroker` dos testes. O banco é a fonte da verdade: o aviso só diz o que mudou.
"""

import asyncio
from collections.abc import Sequence
from typing import Protocol

from app.domain.handoff import HandoffNotice


class RealtimeBroker(Protocol):
    """Distribui os avisos do atendimento aos fluxos abertos neste processo."""

    def subscribe(self) -> "asyncio.Queue[HandoffNotice]":
        """Uma fila nova que passa a receber todos os avisos. O fluxo filtra os seus."""
        ...

    def unsubscribe(self, queue: "asyncio.Queue[HandoffNotice]") -> None:
        """Para de entregar avisos à fila. Chamado no fim de cada fluxo."""
        ...

    async def committed(self, notices: Sequence[HandoffNotice]) -> None:
        """Avisos de uma transação que acabou de confirmar, neste processo.

        O `NOTIFY` já foi feito dentro da transação. O `PostgresNotifyBroker` recebe o aviso
        pelo `LISTEN` e só entrega por aqui enquanto o ouvinte está fora do ar; o
        `InMemoryBroker` entrega sempre.
        """
        ...

    @property
    def listener_up(self) -> bool:
        """Se o ouvinte entre processos está conectado. Vai na métrica da seção 29.12."""
        ...
