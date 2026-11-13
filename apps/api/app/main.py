"""Ponto de entrada da API: monta o app FastAPI e o expõe em `app`. Seção 6 do SDD.

É a raiz da camada de controle (seção 6.2). Junta os middlewares de `app.core.middleware`, o
CORS do Starlette, os tratadores de erro de `app.core.errors` e os 16 roteadores de
`app.controllers`, mais o do webhook do WhatsApp com o canal ligado. O Uvicorn importa
`app.main:app`, no `CMD` do `Dockerfile` e no `uv run uvicorn` local. Os testes chamam
`create_app()` para ter um app novo com a configuração do momento.

Importar este módulo não carrega o SQLAlchemy, o asyncpg nem o LangChain: o `lifespan`, a raiz
de composição e os controladores importam serviços e adaptadores dentro das funções. Assim o
`/health` responde mesmo sem banco, e `tests/unit/test_health.py` confere isso.
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.controllers.account import router as account_router
from app.controllers.admin_documents import router as admin_documents_router
from app.controllers.admin_handoffs import router as admin_handoffs_router
from app.controllers.admin_insights import router as admin_insights_router
from app.controllers.admin_privacy import router as admin_privacy_router
from app.controllers.admin_probe import router as admin_probe_router
from app.controllers.attendance import router as attendance_router
from app.controllers.auth import router as auth_router
from app.controllers.conversations import router as conversations_router
from app.controllers.handoff import router as handoff_router
from app.controllers.health import router as health_router
from app.controllers.legal import router as legal_router
from app.controllers.metrics import router as metrics_router
from app.controllers.privacy import router as privacy_router
from app.controllers.readiness import router as readiness_router
from app.controllers.registration import router as registration_router
from app.controllers.whatsapp import router as whatsapp_router
from app.core.config import edge_guard_secret, require_safeguards
from app.core.container import ensure_ai_runtime, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import ApiGuardMiddleware, RequestIdMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Provedores, workflows e o pool do banco nascem aqui e vivem o processo. Seção 6.4.

    O FastAPI roda o trecho antes do `yield` uma vez, quando o servidor sobe o app, e o
    `finally` uma vez, quando ele desliga. Um `TestClient` usado fora de `with` não roda o
    `lifespan`: o runtime de IA nasce no primeiro uso, e cada sessão abre a própria conexão.

    1. Monta o `AiRuntime` (provedor de chat com o circuit breaker, `QaWorkflow` e grafo do
       cadastro) e o guarda em `app.state` (seção 6.2). Um runtime que o teste já pôs lá fica.
    2. Com `DATABASE_URL`, abre o pool do processo. O pool não conecta ao abrir.
    3. Marca como `failed` as versões de documento presas em `processing` há mais de 15
       minutos (seção 7.3). Uma falha aqui só gera o log `ingestion.stale_check_failed`: a API
       sobe com o banco fora, e o `/ready` mostra o problema.
    4. Abre o ouvinte `LISTEN atrium_handoff` do atendimento humano, fora do pool, e a
       varredura de 30 segundos (seções 29.5 e 29.6, ADR-016). Os dois rodam mesmo com
       `HANDOFF_ENABLED` desligado: a varredura então encerra a fila que sobrou.
    5. Com `WHATSAPP_ENABLED`, abre o laço do canal WhatsApp: o processador da caixa de
       entrada, o repasse do atendimento e o enviador, com o adaptador da Graph API (seção 30).
    6. No desligamento, para o laço do WhatsApp, a varredura e o ouvinte, fecha o pool e
       espera os rastros pendentes do LangSmith, para não perder rastros num deploy (18.4).
    """
    # 1. Mesmo objeto que `get_ai_runtime` entrega às rotas, então um circuito só por processo.
    settings = get_settings()
    ensure_ai_runtime(app.state, settings)
    broker = None
    sweeper: asyncio.Task[None] | None = None
    whatsapp_task: asyncio.Task[None] | None = None
    whatsapp_channel = None
    if settings.database_url:
        from app.adapters.clock import SystemClock
        from app.db.session import start_pool
        from app.services.ingestion import fail_stale_processing_versions

        # 2. O pool é deste loop de eventos: as rotas que rodam nele passam a reaproveitá-lo.
        await start_pool(settings.database_url)
        # 3. Relógio real, não o `get_clock`: o `lifespan` não passa pelas dependências.
        try:
            await fail_stale_processing_versions(settings.database_url, SystemClock())
        except Exception:
            structlog.get_logger("atrium").warning("ingestion.stale_check_failed")
        # 4. Um broker que o teste já pôs em `app.state` fica.
        from app.adapters.realtime import PostgresNotifyBroker
        from app.services.handoff_sweep import HandoffSweeper

        if getattr(app.state, "realtime_broker", None) is None:
            broker = PostgresNotifyBroker(settings.database_url)
            broker.start()
            app.state.realtime_broker = broker
        sweeper = asyncio.create_task(
            HandoffSweeper(
                database_url=settings.database_url,
                clock=SystemClock(),
                enabled=settings.handoff_enabled,
                broker=app.state.realtime_broker,
            ).run()
        )
        # 5. O canal WhatsApp: processador, repasse e enviador num laço (ADR-017). Um laço
        # que o teste já pôs em `app.state` fica.
        if settings.whatsapp_enabled and getattr(app.state, "whatsapp_worker", None) is None:
            from app.adapters.whatsapp_cloud import MetaCloudApiChannel
            from app.core.container import build_whatsapp_worker

            whatsapp_channel = MetaCloudApiChannel(
                access_token=settings.whatsapp_access_token,
                phone_number_id=settings.whatsapp_phone_number_id,
                graph_version=settings.whatsapp_graph_version,
            )
            worker = build_whatsapp_worker(
                settings,
                runtime=app.state.ai_runtime,
                broker=app.state.realtime_broker,
                channel=whatsapp_channel,
            )
            app.state.whatsapp_worker = worker
            whatsapp_task = asyncio.create_task(worker.run())
    try:
        yield
    finally:
        # 6. O Uvicorn chega aqui no desligamento, depois de encerrar os pedidos em curso.
        if whatsapp_task is not None:
            whatsapp_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await whatsapp_task
        if whatsapp_channel is not None:
            await whatsapp_channel.aclose()
        if sweeper is not None:
            sweeper.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await sweeper
        if broker is not None:
            await broker.close()
        if settings.database_url:
            from app.db.session import close_pool

            await close_pool(settings.database_url)
        from app.adapters.langsmith_tracing import wait_for_all_tracers

        wait_for_all_tracers()


def create_app() -> FastAPI:
    """Monta o app com a configuração atual e o devolve sem subir nada.

    1. Lê a configuração e liga o log JSON (seção 18.1).
    2. Em `development` e `production`, levanta `MissingSafeguards` sem o teto de tokens, as
       chaves de HMAC ou o segredo da borda (seções 7.1 e 10.3). Como `app = create_app()`
       roda no import, o Uvicorn nem sobe, o deploy falha e a Railway mantém a versão anterior
       (seção 22.1).
    3. Registra os três middlewares.
    4. Registra o tratador único do envelope de erro (seção 12).
    5. Inclui os roteadores. Nenhum par de método e caminho se repete, então a ordem não
       muda nada; `/v1/me`, por exemplo, tem o `GET` em `auth.py` e o resto em `account.py`.

    O FastAPI também publica `/docs`, `/redoc` e `/openapi.json` em todo ambiente. A Etapa
    15.2 desliga a documentação fora de `local` e `development`.
    """
    # 1. Configuração e log.
    settings = get_settings()
    configure_logging(settings.log_level)
    # 2. Proteções dos ambientes da Railway.
    require_safeguards(settings)
    app = FastAPI(title="Atrium", version=__version__, lifespan=lifespan)
    # 3. Cada `add_middleware` embrulha os anteriores, então o último registrado roda primeiro.
    # No pedido, a ordem fica RequestId → CORS → ApiGuard → tratadores de erro → rota.
    # O guarda fica por dentro: quando ele recusa, o `request_id` já existe.
    app.add_middleware(
        ApiGuardMiddleware,
        web_origin=settings.web_origin,
        edge_secret=edge_guard_secret(settings),
    )
    # CORS só para `WEB_ORIGIN`, com cookies (`allow_credentials`). O tráfego normal é de mesma
    # origem pelo rewrite e não precisa dele (seção 10.3). A preflight `OPTIONS` é respondida
    # aqui, antes do guarda.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Accept", "Content-Type"],
    )
    # Registrado por último, fica por fora de todos: mede, registra o log e põe `x-request-id`
    # em toda resposta, inclusive no 403 do guarda e na preflight do CORS.
    app.add_middleware(RequestIdMiddleware)
    # 4. Os tratadores rodam por dentro dos middlewares: a resposta de erro também ganha o
    # `no-store` de /v1 e o `x-request-id`. Uma exceção que não é de domínio passa direto e
    # vira o 500 em texto puro do Starlette, por fora deles.
    register_exception_handlers(app)
    # 5. Um roteador por arquivo de `app.controllers`.
    app.include_router(health_router)
    app.include_router(readiness_router)
    app.include_router(metrics_router)
    app.include_router(legal_router)
    app.include_router(privacy_router)
    app.include_router(auth_router)
    app.include_router(account_router)
    app.include_router(registration_router)
    app.include_router(conversations_router)
    app.include_router(handoff_router)
    app.include_router(attendance_router)
    app.include_router(admin_probe_router)
    app.include_router(admin_documents_router)
    app.include_router(admin_insights_router)
    app.include_router(admin_privacy_router)
    app.include_router(admin_handoffs_router)
    # O webhook do WhatsApp só existe com o canal ligado: desligado, a rota responde 404.
    if settings.whatsapp_enabled:
        app.include_router(whatsapp_router)
    return app


# O objeto que o Uvicorn serve. Criado no import: uma proteção ausente derruba a subida, não o
# primeiro pedido (seção 7.1).
app = create_app()
