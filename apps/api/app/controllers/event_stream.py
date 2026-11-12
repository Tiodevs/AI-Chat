"""Resposta SSE dos fluxos longos do atendimento humano. Seções 7.1 e 29.6 do SDD.

Camada de controle. `controllers/handoff.py` e `controllers/attendance.py` entregam o gerador
do serviço a `event_stream_response`, que observa a desconexão do navegador como a pergunta
faz (`controllers/conversations.py`) e põe os cabeçalhos do fluxo. Também recusa o fluxo
aberto a partir de outro site: os fluxos são `GET`, e `Sec-Fetch-Site: cross-site` barra uma
navegação vinda de fora (seção 29.8, CSRF).
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable

from fastapi import Request
from fastapi.responses import StreamingResponse

from app.domain.errors import Forbidden
from app.prompts.handoff import CROSS_SITE

# Os mesmos cabeçalhos do fluxo da pergunta. `x-accel-buffering: no` pede a um proxy no caminho
# que não segure os eventos.
STREAM_HEADERS = {"cache-control": "no-store", "x-accel-buffering": "no"}


def refuse_cross_site(request: Request) -> None:
    """403 para um fluxo pedido por outro site (`Sec-Fetch-Site: cross-site`, seção 29.8)."""
    if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
        raise Forbidden(CROSS_SITE)


def event_stream_response(
    request: Request,
    events: Callable[[asyncio.Event], AsyncIterator[str]],
) -> StreamingResponse:
    """Transmite os eventos do serviço até o fim do fluxo ou até o navegador sair.

    1. No primeiro pedaço, uma tarefa passa a observar `http.disconnect`.
    2. O gerador do serviço recebe o evento de desconexão e para quando ele liga.
    3. No fim, normal ou cortado, a tarefa de observação é encerrada.
    """
    disconnected = asyncio.Event()

    async def chunks() -> AsyncIterator[str]:
        # 1.
        watch = asyncio.create_task(_watch_disconnect(request, disconnected))
        try:
            # 2.
            async for chunk in events(disconnected):
                yield chunk
        finally:
            # 3.
            disconnected.set()
            watch.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watch

    return StreamingResponse(chunks(), media_type="text/event-stream", headers=STREAM_HEADERS)


async def _watch_disconnect(request: Request, disconnected: asyncio.Event) -> None:
    """Lê o canal `receive` até `http.disconnect` e liga `disconnected` (seção 6.4)."""
    while not disconnected.is_set():
        message = await request.receive()
        if message["type"] == "http.disconnect":
            disconnected.set()
            return
