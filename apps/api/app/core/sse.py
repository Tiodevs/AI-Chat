"""Formato SSE, manutenção e o relógio do diagnóstico. Seções 7.1 e 12."""

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator, Mapping
from typing import Any

SSE_KEEPALIVE_SECONDS = 15.0
DIAGNOSTIC_TICK_INTERVAL_SECONDS = 1.0
KEEPALIVE_COMMENT = "keepalive"
KEEPALIVE = object()
DISCONNECTED = object()


def format_event(name: str, payload: Mapping[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {name}\ndata: {data}\n\n"


def format_comment(text: str) -> str:
    return f": {text}\n\n"


async def next_stream_item(
    queue: asyncio.Queue[object],
    disconnected: asyncio.Event,
    *,
    interval_seconds: float,
) -> object:
    """Próximo item da fila, a desconexão, ou a manutenção quando o prazo vence."""
    get_task = asyncio.create_task(queue.get())
    stop_task = asyncio.create_task(disconnected.wait())
    try:
        done, _pending = await asyncio.wait(
            {get_task, stop_task},
            timeout=interval_seconds,
            return_when=asyncio.FIRST_COMPLETED,
        )
    finally:
        for pending in (get_task, stop_task):
            if not pending.done():
                pending.cancel()
        for pending in (get_task, stop_task):
            with contextlib.suppress(asyncio.CancelledError):
                await pending
    if get_task in done and not get_task.cancelled():
        return get_task.result()
    if disconnected.is_set():
        return DISCONNECTED
    return KEEPALIVE


async def iter_diagnostic_indexes(interval_seconds: float) -> AsyncIterator[int]:
    for index in (1, 2, 3):
        yield index
        if index < 3:
            await asyncio.sleep(interval_seconds)
