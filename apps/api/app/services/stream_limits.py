"""Limites dos fluxos SSE do atendimento, contados no processo. Seção 29.6 do SDD.

Camada de serviço. `services/handoff.py` pede uma vaga antes de abrir o fluxo do visitante, e
`services/attendance.py`, antes do fluxo do console. Acima de um limite, o pedido responde
429 `rate_limited` com `retry_after_seconds`, ainda como JSON, antes do primeiro byte do
fluxo. Com mais de uma réplica, cada processo conta os próprios fluxos (seção 29.6).

O contador vive no módulo: um por processo, como o circuit breaker do `AiRuntime`. As
operações rodam no loop de eventos sem `await` no meio, então não precisam de trava.
"""

from collections import Counter
from dataclasses import dataclass, field

from app.core.metrics import SSE_STREAMS
from app.domain.errors import RateLimited
from app.domain.handoff import (
    MAX_STREAMS_PER_ATTENDANT,
    MAX_STREAMS_PER_CONVERSATION,
    MAX_STREAMS_PER_PROCESS,
)
from app.prompts.handoff import STREAMS_LIMITED

# Quanto o navegador espera antes de tentar de novo depois do 429 de um fluxo.
_RETRY_AFTER_SECONDS = 15


@dataclass(slots=True)
class StreamLease:
    """Uma vaga ocupada por um fluxo aberto. `release` devolve a vaga uma vez só."""

    limiter: "StreamLimiter"
    kind: str
    key: str
    released: bool = False

    def release(self) -> None:
        """Devolve a vaga e atualiza `atrium_sse_streams`. Chamar de novo não faz nada."""
        if self.released:
            return
        self.released = True
        self.limiter.release(self)


@dataclass(slots=True)
class StreamLimiter:
    """Conta os fluxos abertos por chave e no total do processo."""

    by_key: Counter[str] = field(default_factory=Counter)
    total: int = 0

    def acquire(self, kind: str, key: str) -> StreamLease:
        """Ocupa uma vaga para o fluxo `kind` (`handoff` ou `attendance`) da chave `key`.

        A chave é a conversa no fluxo do visitante e a pessoa no fluxo do console. Levanta
        `RateLimited` acima de 3 por conversa, 2 por atendente ou 300 no processo.
        """
        limit = MAX_STREAMS_PER_CONVERSATION if kind == "handoff" else MAX_STREAMS_PER_ATTENDANT
        bucket = f"{kind}:{key}"
        if self.total >= MAX_STREAMS_PER_PROCESS or self.by_key[bucket] >= limit:
            raise RateLimited(STREAMS_LIMITED, retry_after_seconds=_RETRY_AFTER_SECONDS)
        self.by_key[bucket] += 1
        self.total += 1
        SSE_STREAMS.labels(stream=kind).inc()
        return StreamLease(limiter=self, kind=kind, key=bucket)

    def release(self, lease: StreamLease) -> None:
        """Libera a vaga do fluxo que terminou."""
        self.by_key[lease.key] -= 1
        if self.by_key[lease.key] <= 0:
            del self.by_key[lease.key]
        self.total = max(0, self.total - 1)
        SSE_STREAMS.labels(stream=lease.kind).dec()


# O limitador do processo.
LIMITER = StreamLimiter()
