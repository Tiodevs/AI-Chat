"""Raiz de composição: monta as peças de cada rota com o `Depends` do FastAPI. Seção 6.2.

Camada de núcleo, o padrão Composition Root da seção 6.2. Uma rota declara
`Annotated[X, Depends(get_x)]`, e o FastAPI chama `get_x` a cada pedido, resolvendo antes as
dependências dela; dentro de um mesmo pedido, cada função roda uma vez só. Os testes trocam
qualquer peça com `app.dependency_overrides[get_x]`.

Duas vidas:

- o `AiRuntime` (provedor de chat com o circuit breaker, `QaWorkflow` e grafo do cadastro)
  nasce uma vez por app, no `lifespan`, e fica em `app.state`;
- os serviços, o relógio e o orçamento nascem a cada pedido e não guardam estado.

Os serviços e adaptadores são importados dentro das funções: importar a API para o
`/health` não carrega o LangChain nem o SQLAlchemy. Por isso os `get_*` de serviço devolvem
`Any`, e o mypy não confere as chamadas dos controladores a esses serviços.

Nem toda rota passa por aqui. `auth.py`, `account.py`, `privacy.py`, `admin_guard.py`,
`admin_probe.py` e `readiness.py` criam o serviço dentro da própria função, só com
`get_settings` e `get_clock`.
"""

import threading
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import Depends, Request
from starlette.datastructures import State

from app.adapters.clock import SystemClock
from app.core.config import Settings
from app.ports.clock import Clock

if TYPE_CHECKING:
    from app.ports.chat import ChatProvider
    from app.ports.embedding import EmbeddingProvider
    from app.workflows.qa import QaWorkflow
    from app.workflows.registration import RegistrationWorkflow

# `threading.Lock`, não `asyncio.Lock`: o FastAPI roda uma dependência `def` numa thread do
# threadpool, então dois pedidos podem chegar a `ensure_ai_runtime` ao mesmo tempo.
_RUNTIME_LOCK = threading.Lock()


@dataclass(frozen=True, slots=True)
class Container:
    """O que as rotas de infraestrutura recebem: hoje, só a configuração.

    `/health`, `/ready` e `/metrics` o pedem com `get_container`.
    """

    settings: Settings


@dataclass(frozen=True, slots=True)
class AiRuntime:
    """O que vive o processo inteiro: o provedor de chat com o circuit breaker e os workflows.

    Um provedor novo por pedido zeraria o circuito, e a regra de 5 falhas seguidas e 60 s
    aberto nunca dispararia. O cadastro e as perguntas usam o mesmo provedor, então o mesmo
    circuito. O grafo do cadastro é compilado uma vez. Seções 6.2 e 7.1 do SDD.
    """

    chat: "ChatProvider"
    qa_workflow: "QaWorkflow"
    registration_workflow: "RegistrationWorkflow"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """A configuração do processo, lida uma vez (`lru_cache`).

    Os testes mudam o ambiente e chamam `get_settings.cache_clear()` para reler.
    """
    return Settings()


def get_container(settings: Annotated[Settings, Depends(get_settings)]) -> Container:
    """Embrulha a configuração para as rotas de infraestrutura."""
    return Container(settings=settings)


def get_clock() -> Clock:
    """O relógio do sistema. Os testes o trocam por um relógio parado (`dependency_overrides`)."""
    return SystemClock()


def build_ai_runtime(
    settings: Settings,
    *,
    chat: "ChatProvider | None" = None,
    embeddings: "EmbeddingProvider | None" = None,
) -> AiRuntime:
    """Monta o runtime. Os testes passam provedores falsos no lugar dos da configuração.

    1. Escolhe os provedores de chat e de embedding por `APP_AI_ADAPTER`, salvo os que o
       teste passou. Com `gemini` e sem chave, vêm os provedores indisponíveis, que só falham
       na chamada (seção 17).
    2. Pega o tracer do LangSmith ou, sem tracing, o `NullTracer`.
    3. Monta o `QaWorkflow`, com a busca híbrida do `RetrievalService`, e o
       `RegistrationWorkflow`, os dois sobre o mesmo provedor de chat.

    Não chama o modelo nem o banco: só cria os objetos.
    """
    # Import tardio: subir a API para /health não carrega o LangChain nem o SQLAlchemy.
    from app.adapters.chat_factory import build_chat_provider
    from app.adapters.embedding_factory import build_embedding_provider
    from app.adapters.langsmith_tracing import tracer_for
    from app.ports.tracing import NullTracer
    from app.services.retrieval import RetrievalService
    from app.workflows.qa import QaWorkflow
    from app.workflows.registration import RegistrationWorkflow

    # 1. Provedores.
    shared_chat = chat or build_chat_provider(settings)
    query_embeddings = embeddings or build_embedding_provider(settings)
    # 2. Tracer.
    tracer = tracer_for(settings) or NullTracer()
    # 3. Workflows. A busca e o workflow recebem o mesmo piso de similaridade.
    return AiRuntime(
        chat=shared_chat,
        qa_workflow=QaWorkflow(
            shared_chat,
            query_embeddings,
            RetrievalService(
                settings.database_url,
                query_embeddings,
                minimum_similarity=settings.retrieval_min_similarity,
            ),
            minimum_similarity=settings.retrieval_min_similarity,
            tracer=tracer,
        ),
        registration_workflow=RegistrationWorkflow(shared_chat, tracer=tracer),
    )


def ensure_ai_runtime(state: State, settings: Settings) -> AiRuntime:
    """O runtime do app. O `lifespan` monta na subida; sem ele, monta no primeiro uso.

    Confere duas vezes, fora e dentro da trava: com o runtime pronto, o caminho comum não
    espera a trava, e só uma thread monta o primeiro. Um runtime que o teste já pôs em `state`
    fica como está.
    """
    runtime = getattr(state, "ai_runtime", None)
    if isinstance(runtime, AiRuntime):
        return runtime
    with _RUNTIME_LOCK:
        runtime = getattr(state, "ai_runtime", None)
        if not isinstance(runtime, AiRuntime):
            runtime = build_ai_runtime(settings)
            state.ai_runtime = runtime
    return runtime


def get_ai_runtime(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AiRuntime:
    """O runtime guardado no `app.state` do app que recebeu o pedido."""
    return ensure_ai_runtime(request.app.state, settings)


def get_registration_service(
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
    runtime: Annotated[AiRuntime, Depends(get_ai_runtime)],
) -> Any:
    """`RegistrationService` novo a cada pedido, sobre o grafo do cadastro do `AiRuntime`.

    O orçamento diário é o mesmo das perguntas (seção 7.2).
    """
    from app.adapters.password_hasher import get_password_hasher
    from app.services.budget import PostgresTokenBudget
    from app.services.registration import RegistrationService

    return RegistrationService(
        database_url=settings.database_url,
        clock=clock,
        hasher=get_password_hasher(),
        hmac_key=settings.rate_limit_hmac_key,
        app_env=settings.app_env,
        workflow=runtime.registration_workflow,
        budget=PostgresTokenBudget(
            settings.database_url,
            clock,
            settings.llm_daily_token_budget,
        ),
    )


def get_feedback_sink(settings: Annotated[Settings, Depends(get_settings)]) -> Any:
    """Destino do feedback do visitante: o LangSmith com tracing ligado, senão o `Noop`.

    O cliente do LangSmith é guardado em `app.adapters.langsmith_tracing` e só muda quando a
    configuração do LangSmith muda.
    """
    from app.adapters.langsmith_tracing import feedback_sink_for

    return feedback_sink_for(settings)


def get_qa_workflow(runtime: Annotated[AiRuntime, Depends(get_ai_runtime)]) -> Any:
    """O `QaWorkflow` do runtime, numa dependência própria para o teste trocar só ele."""
    return runtime.qa_workflow


def get_conversation_service(
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
    workflow: Annotated[Any, Depends(get_qa_workflow)],
    feedback_sink: Annotated[Any, Depends(get_feedback_sink)],
) -> Any:
    """`ConversationService` novo a cada pedido, com o workflow do runtime.

    Recebe também o destino do feedback, a chave de HMAC dos limites, a chave do pseudônimo
    dos rastros e o orçamento diário de tokens (seção 7.1).
    """
    from app.services.budget import PostgresTokenBudget
    from app.services.conversations import ConversationService

    return ConversationService(
        database_url=settings.database_url,
        clock=clock,
        hmac_key=settings.rate_limit_hmac_key,
        app_env=settings.app_env,
        workflow=workflow,
        feedback_sink=feedback_sink,
        pseudonym_key=settings.pseudonym_key,
        budget=PostgresTokenBudget(
            settings.database_url,
            clock,
            settings.llm_daily_token_budget,
        ),
    )


def get_document_admin_service(
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> Any:
    """`DocumentAdminService` com a ingestão da seção 7.3.

    O provedor de embedding e o extrator de texto nascem a cada pedido, fora do `AiRuntime`.
    A ingestão roda depois, numa tarefa de fundo, com esses mesmos objetos.
    """
    from app.adapters.embedding_factory import build_embedding_provider
    from app.adapters.langsmith_tracing import tracer_for
    from app.adapters.text_extractor import FileTextExtractor
    from app.ports.tracing import NullTracer
    from app.services.documents import DocumentAdminService
    from app.services.ingestion import IngestionService

    return DocumentAdminService(
        database_url=settings.database_url,
        clock=clock,
        hmac_key=settings.rate_limit_hmac_key,
        ingestion=IngestionService(
            settings.database_url,
            build_embedding_provider(settings),
            FileTextExtractor(),
            tracer=tracer_for(settings) or NullTracer(),
        ),
    )


def get_insights_service(
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> Any:
    """`InsightsService` da visão geral, da qualidade e do inspetor do admin.

    Recebe a chave do pseudônimo, o teto diário de tokens e o modelo do link do LangSmith.
    """
    from app.services.insights import InsightsService

    return InsightsService(
        database_url=settings.database_url,
        clock=clock,
        pseudonym_key=settings.pseudonym_key,
        daily_budget=settings.llm_daily_token_budget,
        run_url_template=settings.langsmith_run_url_template,
    )


def get_privacy_queue_service(
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> Any:
    """`PrivacyQueueService` da fila de pedidos de titular do admin."""
    from app.services.privacy import PrivacyQueueService

    return PrivacyQueueService(database_url=settings.database_url, clock=clock)


def get_realtime_broker(request: Request) -> Any:
    """O broker dos avisos do atendimento humano, um por app (ADR-016).

    O `lifespan` guarda em `app.state` o `PostgresNotifyBroker`, que ouve o `LISTEN`. Sem
    `lifespan`, como num `TestClient` fora de `with`, nasce um `InMemoryBroker` no primeiro
    uso, que entrega os avisos só neste processo.
    """
    from app.adapters.realtime import InMemoryBroker

    broker = getattr(request.app.state, "realtime_broker", None)
    if broker is None:
        broker = InMemoryBroker()
        request.app.state.realtime_broker = broker
    return broker


def get_handoff_service(
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
    broker: Annotated[Any, Depends(get_realtime_broker)],
) -> Any:
    """`HandoffService` do visitante a cada pedido, sem provedor de IA nenhum (FR-21)."""
    from app.services.handoff import HandoffService

    return HandoffService(
        database_url=settings.database_url,
        clock=clock,
        hmac_key=settings.rate_limit_hmac_key,
        enabled=settings.handoff_enabled,
        broker=broker,
    )


def get_attendance_service(
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
    broker: Annotated[Any, Depends(get_realtime_broker)],
) -> Any:
    """`AttendanceService` da equipe e do admin a cada pedido, sem provedor de IA (NFR-17)."""
    from app.services.attendance import AttendanceService

    return AttendanceService(
        database_url=settings.database_url,
        clock=clock,
        hmac_key=settings.rate_limit_hmac_key,
        pseudonym_key=settings.pseudonym_key,
        broker=broker,
    )
