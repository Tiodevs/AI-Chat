import json
import time
from collections.abc import MutableMapping

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from ulid import ULID

from app.core.context import current_request_id, request_id_var
from app.core.logging import log_http_request
from app.domain.auth import origin_is_allowed
from app.domain.errors import BadOrigin
from app.prompts.auth import BAD_ORIGIN
from app.schemas.errors import ErrorBody, ErrorResponse


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


class ApiGuardMiddleware:
    """Origem nos métodos que mudam estado e Cache-Control nos /v1. Seções 10.3 e NFR-11."""

    def __init__(self, app: ASGIApp, web_origin: str) -> None:
        self.app = app
        self.web_origin = web_origin

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path")
        request_path = path if isinstance(path, str) else ""
        method = scope.get("method")
        http_method = method if isinstance(method, str) else "GET"
        if not origin_is_allowed(
            method=http_method,
            origin=_header(scope, b"origin"),
            web_origin=self.web_origin,
        ):
            await _send_bad_origin(send, cache=_is_v1(request_path))
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start" and _is_v1(request_path):
                headers = MutableHeaders(scope=cast_message(message))
                headers["cache-control"] = "no-store"
            await send(message)

        await self.app(scope, receive, send_wrapper)


def _is_v1(path: str) -> bool:
    return path == "/v1" or path.startswith("/v1/")


def _header(scope: Scope, name: bytes) -> str | None:
    raw_headers = scope.get("headers")
    if not isinstance(raw_headers, list):
        return None
    for item in raw_headers:
        if not isinstance(item, tuple) or len(item) != 2:
            continue
        key, value = item
        if isinstance(key, bytes) and key.lower() == name and isinstance(value, bytes):
            return value.decode("latin-1")
    return None


async def _send_bad_origin(send: Send, *, cache: bool) -> None:
    payload = ErrorResponse(
        error=ErrorBody(
            code=BadOrigin.code,
            message=BAD_ORIGIN,
            request_id=current_request_id(),
        )
    )
    body = json.dumps(payload.model_dump(exclude_none=True)).encode()
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode()),
    ]
    if cache:
        headers.append((b"cache-control", b"no-store"))
    await send({"type": "http.response.start", "status": 403, "headers": headers})
    await send({"type": "http.response.body", "body": body})
