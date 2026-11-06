"""Modo `demo`: chat por regras e embedding lexical, sem modelo. Seções 17 e 21.1."""

import asyncio
import math
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.adapters.chat_factory import build_chat_provider
from app.adapters.demo_chat import DemoChatProvider
from app.adapters.embedding_factory import build_embedding_provider
from app.adapters.lexical_embedding import LexicalEmbeddingProvider, tokens
from app.core.config import Settings
from app.domain.embedding_text import document_embedding_text, query_embedding_text
from app.domain.errors import ProviderUnavailable
from app.domain.fields import SET_FIELDS_TOOL_NAME, read_tool_arguments
from app.ports.chat import Message, RunContext, Tool
from app.prompts.qa import UNTRUSTED_INTRO, untrusted_block
from app.workflows.qa import QuestionClassification
from app.workflows.registration import PhraseText

TOOL = Tool(name=SET_FIELDS_TOOL_NAME, description="", parameters={})


def _run() -> RunContext:
    return RunContext(
        run_id=uuid4(), request_id="demo", prompt_version="test", trace_policy="metadata_only"
    )


def _classify(question: str) -> QuestionClassification:
    return asyncio.run(
        DemoChatProvider().complete_structured(
            [Message(role="system", content="x"), Message(role="user", content=question)],
            QuestionClassification,
            _run(),
        )
    )


@pytest.mark.parametrize(
    ("question", "intent"),
    [
        ("Qual é o horário de visita?", "public_info"),
        ("Onde posso estacionar?", "public_info"),
        ("Estou com dor no peito. Que remédio devo tomar?", "medical_advice"),
        ("Quanto de ibuprofeno posso tomar?", "medical_advice"),
        ("Como vai estar o tempo amanhã?", "other"),
    ],
)
def test_the_classification_follows_the_keyword_rules(question: str, intent: str) -> None:
    result = _classify(question)
    assert result.intent == intent
    assert result.standalone_question == question
    assert result.confidence == 0.9


def test_the_answer_quotes_the_first_block_and_cites_it() -> None:
    content = "# Visitas\n\nHorário geral de visita 11:00–20:00. Silêncio 13:00–14:00."
    prompt = (
        "Qual é o horário de visita?\n\n"
        f"{UNTRUSTED_INTRO}\n\n{untrusted_block(2, 'Horário', content)}\n\n"
        f"{untrusted_block(5, 'Outro', 'Texto qualquer.')}"
    )

    async def collect() -> str:
        parts = [
            token
            async for token in DemoChatProvider().stream(
                [Message(role="user", content=prompt)], _run()
            )
        ]
        return "".join(parts)

    assert asyncio.run(collect()) == "Horário geral de visita 11:00–20:00. [2]"


def test_without_context_the_stream_is_unavailable() -> None:
    async def collect() -> None:
        async for _token in DemoChatProvider().stream(
            [Message(role="user", content="sem blocos")], _run()
        ):
            pass

    with pytest.raises(ProviderUnavailable):
        asyncio.run(collect())


@pytest.mark.parametrize(
    ("step", "text", "expected"),
    [
        ("full_name", "Ana Souza", {"full_name": "Ana Souza"}),
        ("email", "meu e-mail é ana.souza@example.com", {"email": "ana.souza@example.com"}),
        ("phone", "pular", {"skip_current": True}),
        ("phone", "(555) 014-2600", {"phone": "(555) 014-2600"}),
        ("visitor_type", "sou acompanhante", {"visitor_type": "caregiver"}),
        ("visitor_type", "prefiro não dizer", {"skip_current": True}),
        ("visit_reason", "vim para um exame", {"visit_reason": "exam_or_test"}),
    ],
)
def test_registration_fields_follow_the_current_step(
    step: str, text: str, expected: dict[str, object]
) -> None:
    result = asyncio.run(
        DemoChatProvider().complete_with_tools(
            [
                Message(role="system", content=f"Instruções.\nPasso atual: {step}."),
                Message(role="user", content=text),
            ],
            [TOOL],
            _run(),
        )
    )
    assert result.name == SET_FIELDS_TOOL_NAME
    assert result.arguments == expected
    # A saída passa pela mesma lista de permissão de qualquer modelo (seção 10.2).
    assert read_tool_arguments(result.arguments).rejected is False


def test_registration_phrases_fall_back_to_the_fixed_copy() -> None:
    with pytest.raises(ProviderUnavailable):
        asyncio.run(
            DemoChatProvider().complete_structured(
                [Message(role="user", content="passo: email")], PhraseText, _run()
            )
        )


def test_lexical_embeddings_bring_shared_words_close() -> None:
    provider = LexicalEmbeddingProvider()

    async def similarity(query: str, title: str, heading: str, content: str) -> float:
        left = await provider.embed_query(query_embedding_text(query))
        right = (
            await provider.embed_documents([document_embedding_text(title, heading, content)])
        )[0]
        return sum(a * b for a, b in zip(left, right, strict=True))

    visiting = asyncio.run(
        similarity("Qual é o horário de visita?", "Visitas", "Horário", "Horário geral de visita.")
    )
    parking = asyncio.run(
        similarity("Qual é o horário de visita?", "Estacionamento", "Vagas", "Garagem coberta.")
    )
    assert visiting > 0.5
    assert visiting > parking
    vector = asyncio.run(provider.embed_query("horário"))
    assert math.isclose(sum(value * value for value in vector), 1.0)
    assert tokens("Qual é o Horário de VISITA?") == ["horario", "visita"]


def test_the_demo_adapter_is_wired_and_never_runs_in_the_cloud() -> None:
    settings = Settings(app_ai_adapter="demo", app_env="test", database_url="")
    assert isinstance(build_chat_provider(settings), DemoChatProvider)
    assert isinstance(build_embedding_provider(settings), LexicalEmbeddingProvider)
    for environment in ("development", "production"):
        with pytest.raises(ValidationError):
            Settings(app_ai_adapter="demo", app_env=environment, database_url="")
