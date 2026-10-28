from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Any

from fastapi import Depends

from app.adapters.clock import SystemClock
from app.core.config import Settings
from app.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class Container:
    settings: Settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def get_container(settings: Annotated[Settings, Depends(get_settings)]) -> Container:
    return Container(settings=settings)


def get_clock() -> Clock:
    return SystemClock()


def get_registration_service(
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> Any:
    from app.adapters.chat_factory import build_chat_provider
    from app.adapters.langsmith_tracing import tracer_for
    from app.adapters.password_hasher import get_password_hasher
    from app.ports.tracing import NullTracer
    from app.services.registration import RegistrationService
    from app.workflows.registration import RegistrationWorkflow

    return RegistrationService(
        database_url=settings.database_url,
        clock=clock,
        hasher=get_password_hasher(),
        hmac_key=settings.rate_limit_hmac_key,
        app_env=settings.app_env,
        workflow=RegistrationWorkflow(
            build_chat_provider(settings),
            tracer=tracer_for(settings) or NullTracer(),
        ),
    )


def get_feedback_sink(settings: Annotated[Settings, Depends(get_settings)]) -> Any:
    from app.adapters.langsmith_tracing import feedback_sink_for

    return feedback_sink_for(settings)


def get_qa_workflow(settings: Annotated[Settings, Depends(get_settings)]) -> Any:
    # Import tardio: subir a API para /health não carrega o SQLAlchemy.
    from app.adapters.chat_factory import build_chat_provider
    from app.adapters.embedding_factory import build_embedding_provider
    from app.adapters.langsmith_tracing import tracer_for
    from app.ports.tracing import NullTracer
    from app.services.retrieval import RetrievalService
    from app.workflows.qa import QaWorkflow

    embeddings = build_embedding_provider(settings)
    return QaWorkflow(
        build_chat_provider(settings),
        embeddings,
        RetrievalService(
            settings.database_url,
            embeddings,
            minimum_similarity=settings.retrieval_min_similarity,
        ),
        minimum_similarity=settings.retrieval_min_similarity,
        tracer=tracer_for(settings) or NullTracer(),
    )


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
