"""Formato SSE, manutenção e o relógio do diagnóstico. Seções 7.1 e 12.

Camada de núcleo, sem framework. Quem usa: `app/controllers/conversations.py`, que transforma
os eventos em texto, e `app/services/conversations.py`, que espera o próximo token com
`next_stream_item`. Um evento SSE é a linha `event:`, a linha `data:` e uma linha em branco.
Um comentário começa com `:`, e o leitor do frontend (`apps/web/src/lib/sse.ts`) o pula.
"""

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator, Mapping
from typing import Any

# Seção 7.1: sem token por 15 s, a API manda `: keepalive`, para um proxy não fechar a conexão
# ociosa.
SSE_KEEPALIVE_SECONDS = 15.0
# Seção 12: um `tick` por segundo no `GET /v1/diagnostics/stream`.
DIAGNOSTIC_TICK_INTERVAL_SECONDS = 1.0
KEEPALIVE_COMMENT = "keepalive"
# Sentinelas que `next_stream_item` devolve. Um `object()` só é igual a si mesmo, então nunca
# se confunde com um item da fila; quem recebe compara com `is`.
KEEPALIVE = object()
DISCONNECTED = object()


def format_event(name: str, payload: Mapping[str, Any]) -> str:
    """Monta um evento SSE com a carga em JSON compacto.

    O `json.dumps` escapa as quebras de linha do texto, então a carga cabe numa linha só de
    `data:`. `ensure_ascii=False` mantém os acentos em UTF-8.
    """
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {name}\ndata: {data}\n\n"


def format_comment(text: str) -> str:
    """Monta um comentário SSE, como `: keepalive`."""
    return f": {text}\n\n"


async def next_stream_item(
    queue: asyncio.Queue[object],
    disconnected: asyncio.Event,
    *,
    interval_seconds: float,
) -> object:
    """Próximo item da fila, a desconexão, ou a manutenção quando o prazo vence.

    Devolve o item, `DISCONNECTED` ou `KEEPALIVE`.

    1. Cria uma tarefa para a fila e outra para o evento de desconexão e espera a primeira
       que terminar, por até `interval_seconds`.
    2. Cancela e aguarda a que sobrou, para nenhuma tarefa ficar solta no loop de eventos.
    3. Se a fila e a desconexão terminam juntas, vale o item.

    Cancelar a espera da fila não tira o item dela: o `asyncio.Queue` só entrega o valor a
    quem termina a espera, e o item sai na chamada seguinte.
    """
    # 1.
    get_task = asyncio.create_task(queue.get())
    stop_task = asyncio.create_task(disconnected.wait())
    try:
        done, _pending = await asyncio.wait(
            {get_task, stop_task},
            timeout=interval_seconds,
            return_when=asyncio.FIRST_COMPLETED,
        )
    finally:
        # 2. Roda também quando quem chamou é cancelado no meio da espera.
        for pending in (get_task, stop_task):
            if not pending.done():
                pending.cancel()
        for pending in (get_task, stop_task):
            with contextlib.suppress(asyncio.CancelledError):
                await pending
    # 3.
    if get_task in done and not get_task.cancelled():
        return get_task.result()
    if disconnected.is_set():
        return DISCONNECTED
    return KEEPALIVE


async def iter_diagnostic_indexes(interval_seconds: float) -> AsyncIterator[int]:
    """Os índices 1, 2 e 3, com `interval_seconds` entre eles e sem espera depois do último.

    A fumaça do deploy usa o intervalo para conferir que o primeiro `tick` chega antes do fim
    do fluxo, sem o rewrite segurar os eventos (seção 22.3).
    """
    for index in (1, 2, 3):
        yield index
        if index < 3:
            await asyncio.sleep(interval_seconds)
