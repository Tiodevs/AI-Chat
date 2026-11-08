"""Circuito do chat: 5 falhas seguidas, aberto por 60 segundos. Seção 7.1 do SDD.

Adaptador de infraestrutura (seção 6.2, padrão Circuit Breaker). Um circuit breaker conta as
falhas seguidas de um provedor. Fechado, deixa as chamadas passarem. Com 5 falhas seguidas,
abre: por 60 s, as chamadas são recusadas sem ir ao provedor, e a pergunta degrada. Passado o
prazo, fecha de novo com a contagem ainda no limite: a próxima falha o reabre, e só um
sucesso zera a conta.

Quem usa: `GeminiChatProvider`, que tem um circuito por instância. O gauge
`atrium_llm_circuit_open` (seção 18.3) vale 1 com o circuito aberto e 0 fechado. Sem `await`
nos métodos, então o loop de eventos não intercala duas atualizações.
"""

from datetime import datetime, timedelta

from app.core.metrics import LLM_CIRCUIT_OPEN
from app.ports.clock import Clock

# Seção 7.1, "Orçamento e degradação".
FAILURE_LIMIT = 5
OPEN_SECONDS = 60.0


class CircuitBreaker:
    """Conta falhas seguidas e recusa chamadas pelo tempo em que o circuito fica aberto.

    O relógio vem da porta `Clock`, para os testes avançarem o tempo sem esperar.
    """

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
        """Diz se a próxima chamada pode ir ao provedor.

        Quando o prazo de abertura passa, o circuito fecha e o gauge volta a 0. A contagem de
        falhas não zera nesse momento: se a primeira chamada depois do prazo falhar, ela já
        alcança o limite e o circuito abre de novo por mais 60 s. Só um sucesso zera a conta.
        """
        if self._open_until is None:
            return True
        if self._clock.now() >= self._open_until:
            self._open_until = None
            LLM_CIRCUIT_OPEN.set(0)
            return True
        return False

    def record_success(self) -> None:
        """Zera as falhas seguidas e fecha o circuito."""
        self._consecutive_failures = 0
        self._open_until = None
        LLM_CIRCUIT_OPEN.set(0)

    def record_failure(self) -> None:
        """Conta uma falha e abre o circuito ao alcançar o limite, marcando o gauge com 1."""
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._failure_limit:
            self._open_until = self._clock.now() + timedelta(seconds=self._open_seconds)
            LLM_CIRCUIT_OPEN.set(1)
