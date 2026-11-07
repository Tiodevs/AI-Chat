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

_RUNTIME_LOCK = threading.Lock()


@dataclass(frozen=True, slots=True)
class Container:
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
    return Settings()


def get_container(settings: Annotated[Settings, Depends(get_settings)]) -> Container:
    return Container(settings=settings)


def get_clock() -> Clock:
    return SystemClock()


def build_ai_runtime(
    settings: Settings,
    *,
    chat: "ChatProvider | None" = None,
    embeddings: "EmbeddingProvider | None" = None,
) -> AiRuntime:
    """Monta o runtime. Os testes passam provedores falsos no lugar dos da configuração."""
    # Import tardio: subir a API para /health não carrega o LangChain nem o SQLAlchemy.
    from app.adapters.chat_factory import build_chat_provider
    from app.adapters.embedding_factory import build_embedding_provider
    from app.adapters.langsmith_tracing import tracer_for
    from app.ports.tracing import NullTracer
    from app.services.retrieval import RetrievalService
    from app.workflows.qa import QaWorkflow
    from app.workflows.registration import RegistrationWorkflow

    shared_chat = chat or build_chat_provider(settings)
    query_embeddings = embeddings or build_embedding_provider(settings)
    tracer = tracer_for(settings) or NullTracer()
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
    """O runtime do app. O `lifespan` monta na subida; sem ele, monta no primeiro uso."""
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
    return ensure_ai_runtime(request.app.state, settings)


def get_registration_service(
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
    runtime: Annotated[AiRuntime, Depends(get_ai_runtime)],
) -> Any:
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
    from app.adapters.langsmith_tracing import feedback_sink_for

    return feedback_sink_for(settings)


def get_qa_workflow(runtime: Annotated[AiRuntime, Depends(get_ai_runtime)]) -> Any:
    return runtime.qa_workflow


def get_conversation_service(
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
    workflow: Annotated[Any, Depends(get_qa_workflow)],
    feedback_sink: Annotated[Any, Depends(get_feedback_sink)],
) -> Any:
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
    from app.services.privacy import PrivacyQueueService

    return PrivacyQueueService(database_url=settings.database_url, clock=clock)
