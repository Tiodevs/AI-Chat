"""Formato do fluxo e o comentário de manutenção. Seção 7.1 do SDD."""

import asyncio
import json
from uuid import UUID

from app.controllers.conversations import render_ask_event
from app.core.sse import (
    DIAGNOSTIC_TICK_INTERVAL_SECONDS,
    DISCONNECTED,
    KEEPALIVE,
    SSE_KEEPALIVE_SECONDS,
    format_comment,
    format_event,
    iter_diagnostic_indexes,
    next_stream_item,
)
from app.services.conversation_events import CommentEvent, DoneEvent, MetaEvent, TokenEvent


def test_intervals_match_the_specification() -> None:
    assert SSE_KEEPALIVE_SECONDS == 15
    assert DIAGNOSTIC_TICK_INTERVAL_SECONDS == 1


def test_sse_frame_and_keepalive_comment() -> None:
    frame = format_event("meta", {"message_id": "abc", "request_id": "req"})
    assert frame == 'event: meta\ndata: {"message_id":"abc","request_id":"req"}\n\n'
    assert format_comment("keepalive") == ": keepalive\n\n"


def test_render_keeps_meta_token_done_and_the_comment() -> None:
    meta = render_ask_event(
        MetaEvent(message_id=UUID("00000000-0000-4000-8000-0000000000aa"), request_id="req")
    )
    assert meta.startswith("event: meta\n")
    token = render_ask_event(TokenEvent("11:00"))
    assert json.loads(token.split("data: ", 1)[1]) == {"text": "11:00"}
    done = render_ask_event(DoneEvent("answered"))
    assert "answered" in done
    assert render_ask_event(CommentEvent("keepalive")) == ": keepalive\n\n"


def test_wait_returns_the_item_keepalive_or_disconnect() -> None:
    assert asyncio.run(_wait()) == ["token", KEEPALIVE, DISCONNECTED]


def test_diagnostics_yields_three_indexes() -> None:
    assert asyncio.run(_ticks()) == [1, 2, 3]


async def _wait() -> list[object]:
    queue: asyncio.Queue[object] = asyncio.Queue()
    disconnected = asyncio.Event()
    await queue.put("token")
    first = await next_stream_item(queue, disconnected, interval_seconds=0.01)
    keepalive = await next_stream_item(queue, disconnected, interval_seconds=0.01)
    disconnected.set()
    closed = await next_stream_item(queue, disconnected, interval_seconds=1)
    return [first, keepalive, closed]


async def _ticks() -> list[int]:
    return [index async for index in iter_diagnostic_indexes(0)]
