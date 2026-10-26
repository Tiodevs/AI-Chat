import time
from collections.abc import MutableMapping

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from ulid import ULID

from app.core.context import request_id_var
from app.core.logging import log_http_request


def route_template(scope: Scope) -> str:
    route = scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str):
        return path
    raw_path = scope.get("path")
    if isinstance(raw_path, str):
        return raw_path
    return ""


class RequestIdMiddleware:
    """Gera o request_id, devolve em x-request-id e registra o pedido. Seção 18.1."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(ULID())
        token = request_id_var.set(request_id)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers = MutableHeaders(scope=cast_message(message))
                headers.append("x-request-id", request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = int((time.perf_counter() - started) * 1000)
            try:
                log_http_request(
                    request_id=request_id,
                    route=route_template(scope),
                    status_code=status_code,
                    duration_ms=duration_ms,
                )
            finally:
                request_id_var.reset(token)
                structlog.contextvars.clear_contextvars()


def cast_message(message: Message) -> MutableMapping[str, object]:
    return message
