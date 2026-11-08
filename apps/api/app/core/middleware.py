"""Middlewares ASGI da API: `request_id`, métricas HTTP e o guarda de `/v1`. Seções 10.3 e 18.

Camada de núcleo. `create_app` registra os dois, e a ordem no pedido é `RequestIdMiddleware`
→ CORS → `ApiGuardMiddleware` → tratadores de erro → rota. Os dois são ASGI puros: recebem
`scope` (o pedido), `receive` e `send`, e trocam o `send` por um `send_wrapper` para mexer
nos cabeçalhos da mensagem `http.response.start` antes de ela sair.

As regras de origem e do segredo da borda são funções puras de `app/domain/auth.py`; os
textos de erro ficam em `app/prompts/auth.py`.
"""

import json
import time
from collections.abc import MutableMapping

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from ulid import ULID

from app.core.context import current_request_id, request_id_var
from app.core.logging import log_http_request
from app.core.metrics import HTTP_DURATION, HTTP_REQUESTS
from app.domain.auth import EDGE_HEADER, edge_is_trusted, origin_is_allowed
from app.domain.errors import BadOrigin, Forbidden
from app.prompts.auth import BAD_ORIGIN, EDGE_FORBIDDEN
from app.schemas.errors import ErrorBody, ErrorResponse


def route_template(scope: Scope) -> str:
    """Modelo do caminho da rota casada, como `/v1/conversations/{conversation_id}`.

    O roteador grava `scope["route"]` no mesmo dicionário que o middleware recebeu, então o
    valor já existe depois de `await self.app(...)`. Sem rota casada, como num 403 do guarda
    ou num 404, vale o caminho cru. A métrica usa `unmatched` nesse caso (`_observe_http`).
    """
    route = scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str):
        return path
    raw_path = scope.get("path")
    if isinstance(raw_path, str):
        return raw_path
    return ""


class RequestIdMiddleware:
    """Gera o request_id, devolve em x-request-id e registra o pedido. Seção 18.1.

    Por pedido HTTP:

    1. Gera um ULID novo, que ordena por tempo, e o grava em `request_id_var` e no contexto do
       `structlog`. Um id mandado pelo cliente nunca é aceito.
    2. Troca o `send` por um que guarda o status e põe `x-request-id` na resposta.
    3. No fim, mesmo com exceção, observa as métricas HTTP, escreve a linha `http.request` e
       desfaz o contexto.

    O `finally` só roda quando o app termina tudo o que fez no pedido. Isso inclui o fluxo SSE
    inteiro e as tarefas de fundo (`BackgroundTasks`), que o Starlette roda depois de enviar a
    resposta: a duração medida inclui a ingestão de um upload.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # `lifespan` e `websocket` passam direto: só pedido HTTP ganha `request_id`.
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 1. Limpa o contexto antes e depois: nenhum campo de um pedido vaza para outro.
        request_id = str(ULID())
        token = request_id_var.set(request_id)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.perf_counter()
        # Fica 500 se o app levantar antes de responder, o status que o Starlette devolve.
        status_code = 500

        # 2. `MutableHeaders(scope=...)` edita a lista `headers` da própria mensagem.
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
            # 3. O `reset` devolve o valor anterior do `ContextVar` mesmo se o log falhar.
            elapsed = time.perf_counter() - started
            duration_ms = int(elapsed * 1000)
            _observe_http(scope, status_code, elapsed)
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


def _observe_http(scope: Scope, status_code: int, elapsed: float) -> None:
    """Conta o pedido e mede a duração por rota (seção 18.3).

    Sem rota casada, o rótulo é `unmatched`, para um caminho com id cru nunca virar rótulo.
    """
    route = getattr(scope.get("route"), "path", None)
    label = route if isinstance(route, str) else "unmatched"
    method = scope.get("method")
    HTTP_REQUESTS.labels(
        route=label,
        method=method if isinstance(method, str) else "GET",
        status=str(status_code),
    ).inc()
    HTTP_DURATION.labels(route=label).observe(elapsed)


def cast_message(message: Message) -> MutableMapping[str, object]:
    """Só ajusta o tipo da mensagem para o `MutableHeaders(scope=...)`, sem copiar nada."""
    return message


class ApiGuardMiddleware:
    """Segredo da borda e origem nos /v1, e Cache-Control. Seções 10.3 e NFR-11.

    Com `edge_secret`, um pedido a /v1 sem o cabeçalho da Vercel recebe 403: quem chama a
    Railway direto não forja o `x-forwarded-for` dos limites de taxa. `/health`, `/ready` e
    `/metrics` ficam fora, para a Railway e o Prometheus.

    Por pedido HTTP, nesta ordem:

    1. Em `/v1`, confere `x-atrium-edge` em tempo constante. Com `edge_secret` vazio, como em
       `local` e `test` (`edge_guard_secret`), o portão fica aberto. Recusa: 403 `forbidden`.
    2. Em qualquer caminho, `POST`, `PUT`, `PATCH` e `DELETE` precisam de `Origin` igual a
       `WEB_ORIGIN` (NFR-12), o que completa o `SameSite=Lax` contra CSRF. Recusa: 403
       `bad_origin`.
    3. Toda resposta de `/v1` sai com `Cache-Control: no-store`, inclusive a de erro (NFR-11).

    As recusas respondem aqui, com o envelope da seção 12 montado à mão: os tratadores de
    `app.core.errors` ficam por dentro deste middleware e não veriam um erro levantado aqui.
    """

    def __init__(self, app: ASGIApp, web_origin: str, edge_secret: str = "") -> None:
        self.app = app
        self.web_origin = web_origin
        self.edge_secret = edge_secret

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path")
        request_path = path if isinstance(path, str) else ""
        method = scope.get("method")
        http_method = method if isinstance(method, str) else "GET"
        # 1. Segredo da borda, só em /v1.
        if _is_v1(request_path) and not edge_is_trusted(
            presented=_header(scope, EDGE_HEADER.encode()),
            secret=self.edge_secret,
        ):
            await _send_error(send, code=Forbidden.code, message=EDGE_FORBIDDEN, cache=True)
            return
        # 2. Origem em todo método que muda estado, dentro e fora de /v1.
        if not origin_is_allowed(
            method=http_method,
            origin=_header(scope, b"origin"),
            web_origin=self.web_origin,
        ):
            await _send_error(
                send,
                code=BadOrigin.code,
                message=BAD_ORIGIN,
                cache=_is_v1(request_path),
            )
            return

        # 3. Sobrescreve qualquer `Cache-Control` que a rota tenha posto.
        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start" and _is_v1(request_path):
                headers = MutableHeaders(scope=cast_message(message))
                headers["cache-control"] = "no-store"
            await send(message)

        await self.app(scope, receive, send_wrapper)


def _is_v1(path: str) -> bool:
    """`/v1` e tudo abaixo dele. `/v1x` não conta."""
    return path == "/v1" or path.startswith("/v1/")


def _header(scope: Scope, name: bytes) -> str | None:
    """Valor do primeiro cabeçalho `name` do pedido, ou `None`. `name` vem em minúsculas.

    O ASGI entrega nome e valor em bytes. O valor sai decodificado em latin-1, a codificação
    dos cabeçalhos HTTP, que aceita qualquer byte.
    """
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


async def _send_error(send: Send, *, code: str, message: str, cache: bool) -> None:
    """Responde 403 com o envelope da seção 12, antes de o pedido chegar às rotas.

    O `request_id` já existe, porque o `RequestIdMiddleware` roda antes e também põe o
    `x-request-id` nesta resposta. `cache` acrescenta o `no-store` de `/v1`.
    """
    payload = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
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
