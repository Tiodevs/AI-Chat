"""Adaptadores da porta `RealtimeBroker`: `LISTEN/NOTIFY` e memória. ADR-016 do SDD.

Camada de adaptadores. O `lifespan` de `app/main.py` abre o `PostgresNotifyBroker` quando há
`DATABASE_URL` e o fecha no desligamento; sem `lifespan`, como nos testes, a raiz de
composição (`core/container.py:get_realtime_broker`) usa o `InMemoryBroker`.

O `PostgresNotifyBroker` mantém uma conexão asyncpg própria, fora do pool da seção 6.4, com
`LISTEN atrium_handoff`. Quando a conexão cai, ele reconecta com espera crescente, de 1 a 30
segundos, e a métrica `atrium_realtime_listener_up` mostra o estado. Um aviso perdido nesse
meio-tempo chega pela leitura do tique de cada fluxo, em até 15 segundos (seção 29.6).
"""

import asyncio
import contextlib
from collections.abc import Sequence
from typing import Any

import structlog

from app.core.metrics import REALTIME_LISTENER_UP
from app.db.session import adapt_asyncpg_url
from app.domain.handoff import NOTIFY_CHANNEL, HandoffNotice, parse_notice

# Espera entre tentativas de reconexão do ouvinte, dobrando até o teto.
_RETRY_FIRST_SECONDS = 1.0
_RETRY_MAX_SECONDS = 30.0
# De quanto em quanto tempo o laço confere se a conexão do ouvinte continua viva.
_HEALTH_CHECK_SECONDS = 10.0


class InMemoryBroker:
    """Entrega os avisos só neste processo. Serve aos testes e à API sem banco.

    Cada fila recebe todos os avisos, e o fluxo dono da fila filtra os seus.
    """

    def __init__(self) -> None:
        self._queues: set[asyncio.Queue[HandoffNotice]] = set()

    def subscribe(self) -> "asyncio.Queue[HandoffNotice]":
        """Uma fila nova, sem limite de tamanho: um aviso é pequeno e o fluxo o consome."""
        queue: asyncio.Queue[HandoffNotice] = asyncio.Queue()
        self._queues.add(queue)
        return queue

    def unsubscribe(self, queue: "asyncio.Queue[HandoffNotice]") -> None:
        """Tira a fila da distribuição. Uma fila desconhecida não faz nada."""
        self._queues.discard(queue)

    async def committed(self, notices: Sequence[HandoffNotice]) -> None:
        """Entrega cada aviso a todas as filas, na ordem da transação."""
        self.dispatch(notices)

    def dispatch(self, notices: Sequence[HandoffNotice]) -> None:
        """Põe os avisos em cada fila sem esperar. Chamado no loop de eventos dos fluxos."""
        for queue in list(self._queues):
            for notice in notices:
                queue.put_nowait(notice)

    @property
    def listener_up(self) -> bool:
        """Sem ouvinte entre processos, o canal em memória está sempre disponível."""
        return True


class PostgresNotifyBroker(InMemoryBroker):
    """Ouve `LISTEN atrium_handoff` e entrega os avisos aos fluxos do processo. ADR-016.

    1. `start` cria a tarefa do laço, que conecta, registra o ouvinte e confere a conexão a
       cada 10 segundos.
    2. Cada aviso do PostgreSQL chega em `_on_notify`, no loop de eventos da API, e vai para
       as filas dos fluxos.
    3. Uma conexão que cai é fechada e aberta de novo, com espera crescente.
    4. `close` cancela o laço e fecha a conexão, no desligamento.

    O PostgreSQL só entrega o aviso depois do commit e nunca depois de um rollback, então
    nenhum fluxo acorda por algo que não foi gravado.
    """

    def __init__(self, database_url: str) -> None:
        super().__init__()
        self._dsn, self._connect_args = _asyncpg_dsn(database_url)
        self._connection: Any = None
        self._task: asyncio.Task[None] | None = None
        self._up = False
        # Ligado pelo asyncpg quando a conexão do ouvinte fecha, para o laço reconectar na
        # hora, sem esperar a próxima conferência.
        self._lost = asyncio.Event()

    @property
    def listener_up(self) -> bool:
        """Se a conexão do `LISTEN` está aberta agora."""
        return self._up

    async def committed(self, notices: Sequence[HandoffNotice]) -> None:
        """Com o ouvinte no ar, o `LISTEN` entrega; fora do ar, entrega direto aqui.

        Assim, durante uma reconexão, os fluxos deste processo não esperam o tique.
        """
        if not self._up:
            self.dispatch(notices)

    def start(self) -> None:
        """Abre o laço do ouvinte numa tarefa. Chamar duas vezes não abre outro."""
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def close(self) -> None:
        """Cancela o laço e fecha a conexão do ouvinte."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        await self._disconnect()

    async def _run(self) -> None:
        """O laço do ouvinte: conecta, confere e reconecta para sempre (passos 1 e 3)."""
        delay = _RETRY_FIRST_SECONDS
        logger = structlog.get_logger("atrium")
        reconnecting = False
        while True:
            try:
                await self._connect()
                if reconnecting:
                    logger.info("realtime.listener_reconnected")
                reconnecting = True
                delay = _RETRY_FIRST_SECONDS
                while await self._alive():
                    try:
                        await asyncio.wait_for(self._lost.wait(), timeout=_HEALTH_CHECK_SECONDS)
                        break
                    except TimeoutError:
                        continue
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("realtime.listener_failed", error_type=type(exc).__name__)
            await self._disconnect()
            await asyncio.sleep(delay)
            delay = min(delay * 2, _RETRY_MAX_SECONDS)

    async def _connect(self) -> None:
        """Abre a conexão própria e registra `_on_notify` no canal do atendimento."""
        import asyncpg  # type: ignore[import-untyped]

        self._lost = asyncio.Event()
        self._connection = await asyncpg.connect(self._dsn, **self._connect_args)
        self._connection.add_termination_listener(lambda _connection: self._lost.set())
        await self._connection.add_listener(NOTIFY_CHANNEL, self._on_notify)
        self._set_up(True)

    async def _alive(self) -> bool:
        """Confere a conexão com um `SELECT 1`. Uma conexão fechada devolve falso."""
        connection = self._connection
        if connection is None or connection.is_closed():
            return False
        try:
            await asyncio.wait_for(connection.fetchval("SELECT 1"), timeout=5)
        except Exception:
            return False
        return True

    async def _disconnect(self) -> None:
        """Fecha a conexão do ouvinte, se houver, sem levantar erro."""
        connection, self._connection = self._connection, None
        self._set_up(False)
        if connection is not None:
            with contextlib.suppress(Exception):
                await connection.close(timeout=5)

    @property
    def server_pid(self) -> int | None:
        """O pid da conexão do ouvinte no PostgreSQL. Serve ao teste que a derruba."""
        connection = self._connection
        if connection is None or connection.is_closed():
            return None
        return int(connection.get_server_pid())

    def _on_notify(self, _connection: Any, _pid: int, _channel: str, payload: str) -> None:
        """Passo 2: lê a carga e entrega o aviso. Uma carga estranha é ignorada."""
        notice = parse_notice(payload)
        if notice is not None:
            self.dispatch([notice])

    def _set_up(self, value: bool) -> None:
        """Guarda o estado do ouvinte e o publica em `atrium_realtime_listener_up`."""
        self._up = value
        REALTIME_LISTENER_UP.set(1 if value else 0)


def _asyncpg_dsn(database_url: str) -> tuple[str, dict[str, object]]:
    """A URL no formato do asyncpg, sem o `+asyncpg` do SQLAlchemy, e o `ssl` à parte."""
    url, connect_args = adapt_asyncpg_url(database_url)
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url.removeprefix("postgresql+asyncpg://")
    return url, connect_args
