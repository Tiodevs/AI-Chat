"""Varredura do atendimento humano, a cada 30 segundos no `lifespan`. Seção 29.5 do SDD.

Camada de serviço. O `lifespan` de `app/main.py` roda `HandoffSweeper.run` numa tarefa
enquanto a API está no ar, e o script `attendance_dev` não a usa. Cada passo é um `UPDATE`
condicional com `NOTIFY`, numa transação própria, então duas réplicas varrendo ao mesmo tempo
não duplicam efeito. A varredura não grava auditoria, porque não é acesso de uma pessoa: ela
registra log e métrica (seção 29.5, passo 8).
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from uuid import UUID

import structlog

from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.handoff import SWEEP_INTERVAL_SECONDS
from app.ports.clock import Clock
from app.ports.realtime import RealtimeBroker
from app.repositories.handoffs import HandoffRepository
from app.services.handoff import count_close

_Step = Callable[[HandoffRepository, datetime], Awaitable[list[UUID]]]


class HandoffSweeper:
    """Encerra a fila vencida, o visitante ausente e o atendimento parado, e devolve à fila.

    `enabled` é o `HANDOFF_ENABLED`: desligado, a fila encerra como `service_closed`, e os
    atendimentos já assumidos terminam normalmente.
    """

    def __init__(
        self,
        *,
        database_url: str,
        clock: Clock,
        enabled: bool,
        broker: RealtimeBroker,
    ) -> None:
        self._database_url = database_url
        self._clock = clock
        self._enabled = enabled
        self._broker = broker

    async def sweep_once(self) -> dict[str, int]:
        """Roda cada passo uma vez e devolve quantos atendimentos cada um mudou.

        A ordem segue a seção 29.5: espera vencida, visitante ausente, atendimento parado,
        quem atende sem sinal e, com o serviço desligado, a fila que sobrou.
        """
        steps: list[tuple[str, _Step]] = [
            ("queue_timeout", HandoffRepository.sweep_queue_timeout),
            ("visitor_left", HandoffRepository.sweep_visitor_left),
            ("inactivity", HandoffRepository.sweep_inactivity),
            ("attendant_gone", HandoffRepository.sweep_attendant_gone),
        ]
        if not self._enabled:
            steps.append(("service_closed", HandoffRepository.sweep_service_closed))
        changed: dict[str, int] = {}
        for name, step in steps:
            changed[name] = await self._run(name, step)
        return changed

    async def run(self) -> None:
        """O laço do `lifespan`: varre, espera 30 segundos e repete até ser cancelado.

        Uma falha, como o banco fora do ar, vai para o log e não para o laço.
        """
        logger = structlog.get_logger("atrium")
        while True:
            try:
                await self.sweep_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("handoff.sweep_failed", error_type=type(exc).__name__)
            await asyncio.sleep(SWEEP_INTERVAL_SECONDS)

    async def _run(self, name: str, step: _Step) -> int:
        """Um passo numa transação; depois do commit, os avisos, a métrica e o log."""
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            handoffs = HandoffRepository(session)
            changed = await step(handoffs, now)
            notices = list(handoffs.notices)
            closed = [record for record in [await handoffs.get(item) for item in changed] if record]
        if not changed:
            return 0
        await self._broker.committed(notices)
        logger = structlog.get_logger("atrium")
        for record in closed:
            if record.close_reason is not None and record.status == "closed":
                count_close(record)
            else:
                logger.info("handoff.released", handoff_id=str(record.id), reason=name)
        return len(changed)
