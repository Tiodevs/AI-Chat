"""O pipeline de perguntas sem HTTP: portão, abstenção, fundamentação, rastro e uso de tokens.

FR-2, FR-3, FR-4, FR-17 e NFR-13, seções 6.4, 7.1, 10.1, 10.2 e 18.4 do SDD. Monta o
`QaWorkflow` de `app/workflows/qa.py` com o `FakeChatProvider` e os falsos locais
`_Embeddings` (vetor fixo de 3 dimensões), `_Search` (devolve os chunks dados) e
`_RecordingTracer` (guarda os `TraceEvent`). `_parts` e `_run` montam o cenário de cada teste.
Prova o portão por intenção e confiança, a abstenção abaixo do piso, o `grounding_failed`, o
rastro que deixa sair só o que a política permite, a janela do histórico e o uso parcial de
uma resposta cancelada. Também cobre o script `app.scripts.ask`. Não usa banco nem rede.
"""

import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

import pytest

from app.adapters.fake_chat import FakeChatProvider
from app.core.metrics import REGISTRY
from app.domain.embedding_text import query_embedding_text
from app.domain.errors import CircuitOpen, ProviderUnavailable
from app.domain.outcomes import Outcome, gate_outcome
from app.domain.trace_policy import TraceEvent
from app.ports.chat import UsageTally
from app.prompts.qa import (
    ABSTENTION,
    GENERATE_PROMPT_VERSION,
    MEDICAL_ADVICE,
    OFF_TOPIC,
    REWRITE_PROMPT_VERSION,
    UNAVAILABLE,
    UNTRUSTED_INTRO,
)
from app.repositories.retrieval import RetrievedChunk
from app.scripts.ask import format_ask_result, main
from app.workflows.qa import (
    ConversationTurn,
    QaEventSink,
    QaResult,
    QaWorkflow,
    QuestionClassification,
)

_CHUNK = UUID("00000000-0000-4000-8000-000000000001")
_API = Path(__file__).resolve().parents[2]


def test_medical_advice_wins_over_low_confidence() -> None:
    assert gate_outcome("medical_advice", 0.2) is Outcome.REFUSED
    assert gate_outcome("other", 0.95) is Outcome.OFF_TOPIC
    assert gate_outcome("public_info", 0.59) is Outcome.OFF_TOPIC
    assert gate_outcome("public_info", 0.6) is None
    assert gate_outcome("public_info", float("nan")) is Outcome.OFF_TOPIC


def test_medical_question_trace_keeps_only_the_outcome() -> None:
    question = "Estou com dor no peito. Que medicamento devo tomar?"
    chat, embeddings, search = _parts(
        _classification(question, "medical_advice", 0.91),
    )
    tracer = _RecordingTracer()
    run_id = uuid4()
    result = _run(
        chat,
        embeddings,
        search,
        question,
        tracer=tracer,
        run_id=run_id,
        history=(ConversationTurn(role="user", content="histórico clínico secreto"),),
    )
    assert result.outcome is Outcome.REFUSED
    rendered = _trace_text(tracer.events)
    assert question not in rendered
    assert "histórico clínico secreto" not in rendered
    assert "Não posso ajudar com sintomas" not in rendered
    assert "medicamento" not in rendered
    root = tracer.events[0]
    assert root.name == "qa"
    assert root.policy == "metadata_only"
    assert root.run_id == run_id
    assert root.inputs == {}
    assert root.outputs == {}
    assert root.metadata["outcome"] == "refused"
    assert "intent" not in root.metadata
    rewrite = tracer.events[1]
    assert rewrite.name == "qa.rewrite"
    assert rewrite.parent_run_id == run_id
    assert rewrite.inputs == {}
    assert rewrite.outputs == {}
    assert rewrite.metadata["intent"] == "medical_advice"
    assert "standalone_question" not in rewrite.metadata
    assert question not in rewrite.metadata.values()


def test_public_trace_keeps_the_rewrite_and_drops_the_original_question() -> None:
    chat, embeddings, search = _parts(
        _classification("Qual é o horário de visita no domingo?", "public_info", 0.9),
        hits=[_hit("11:00 às 20:00.")],
        tokens=["O horário é 11:00 [1]."],
    )
    tracer = _RecordingTracer()
    result = _run(
        chat,
        embeddings,
        search,
        "E no domingo?",
        tracer=tracer,
        history=(ConversationTurn(role="user", content="Quero visitar alguém."),),
    )
    assert result.outcome is Outcome.ANSWERED
    rendered = _trace_text(tracer.events)
    assert "E no domingo?" not in rendered
    assert "Quero visitar alguém." not in rendered
    assert "Qual é o horário de visita no domingo?" in rendered
    assert "11:00 às 20:00." in rendered
    assert tracer.events[0].policy == "masked"
    assert tracer.events[0].metadata["outcome"] == "answered"
    assert tracer.events[1].name == "qa.rewrite"
    assert tracer.events[1].policy == "metadata_only"


def test_medical_advice_does_not_retrieve_or_generate() -> None:
    chat, embeddings, search = _parts(
        _classification("dor no peito", "medical_advice", 0.2),
    )
    result = _run(chat, embeddings, search, "Estou com dor no peito")
    assert result.outcome is Outcome.REFUSED
    assert result.text == MEDICAL_ADVICE
    assert embeddings.queries == []
    assert search.calls == []
    assert chat.stream_calls == []


def test_other_intent_is_off_topic_without_retrieval() -> None:
    chat, embeddings, search = _parts(_classification("clima", "other", 0.95))
    result = _run(chat, embeddings, search, "Como está o tempo amanhã?")
    assert result.outcome is Outcome.OFF_TOPIC
    assert result.text == OFF_TOPIC
    assert embeddings.queries == []
    assert search.calls == []
    assert chat.stream_calls == []


def test_low_confidence_is_off_topic_without_the_generator() -> None:
    chat, embeddings, search = _parts(_classification("visita", "public_info", 0.59))
    result = _run(chat, embeddings, search, "E no domingo?")
    assert result.outcome is Outcome.OFF_TOPIC
    assert result.text == OFF_TOPIC
    assert chat.stream_calls == []
    assert embeddings.queries == []


def test_similarity_below_the_floor_abstains_without_generating() -> None:
    chat, embeddings, search = _parts(
        _classification("Horário de visita", "public_info", 0.9),
        hits=[_hit(similarity=0.49)],
        tokens=["11:00 [1]."],
    )
    result = _run(chat, embeddings, search, "Qual é o horário de visita?", minimum=0.50)
    assert result.outcome is Outcome.ABSTAINED
    assert result.text == ABSTENTION
    assert chat.stream_calls == []
    assert embeddings.queries == [query_embedding_text("Horário de visita")]


def test_no_hits_abstain_without_generating() -> None:
    chat, embeddings, search = _parts(_classification("arquivo", "public_info", 0.9))
    result = _run(chat, embeddings, search, "Onde fica o arquivo?")
    assert result.outcome is Outcome.ABSTAINED
    assert chat.stream_calls == []


def test_phone_outside_context_is_grounding_failed() -> None:
    chat, embeddings, search = _parts(
        _classification("Telefone da cardiologia", "public_info", 0.9),
        hits=[_hit("A mesa atende no (555) 014-2600.")],
        tokens=["Ligue (555) 019-9999 [1]."],
    )
    result = _run(chat, embeddings, search, "Qual é o telefone direto da cardiologia?")
    assert result.outcome is Outcome.GROUNDING_FAILED
    assert result.text == ABSTENTION
    assert result.citations == ()
    assert len(chat.stream_calls) == 1


def test_answer_without_a_valid_citation_is_grounding_failed() -> None:
    chat, embeddings, search = _parts(
        _classification("Horário de visita", "public_info", 0.9),
        hits=[_hit("11:00 às 20:00.")],
        tokens=["O horário é 11:00."],
    )
    result = _run(chat, embeddings, search, "Qual é o horário de visita?")
    assert result.outcome is Outcome.GROUNDING_FAILED
    assert result.text == ABSTENTION
    assert result.citations == ()


def test_public_info_answers_with_temperature_citation_and_untrusted_context() -> None:
    # A confiança 0,6 é o próprio limiar do portão. Os tokens somam a reescrita (2, 1) e o
    # fluxo (5, 7). O `visitor_type` só entra na reescrita, nunca na geração.
    chat, embeddings, search = _parts(
        _classification("Horário de visita", "public_info", 0.6),
        hits=[_hit("11:00 às 20:00.")],
        tokens=["O horário é 11:00 [1]."],
        structured_usage=(2, 1),
        stream_usage=(5, 7),
    )
    history = (ConversationTurn(role="user", content="Quero visitar alguém."),)
    result = _run(
        chat,
        embeddings,
        search,
        "Qual é o horário?",
        history=history,
        visitor_type="visitor",
    )
    assert result.outcome is Outcome.ANSWERED
    assert result.text == "O horário é 11:00 [1]."
    assert result.input_tokens == 7
    assert result.output_tokens == 8
    assert result.prompt_version == GENERATE_PROMPT_VERSION
    assert [citation.index for citation in result.citations] == [1]
    assert result.citations[0].document_title == "Visitas"
    assert result.citations[0].heading == "Horário"
    rewrite_messages, rewrite_run = chat.structured_calls[0]
    generate_messages, generate_run = chat.stream_calls[0]
    assert rewrite_run.temperature == 0
    assert generate_run.temperature == 0.2
    assert rewrite_run.trace_policy == "metadata_only"
    assert generate_run.trace_policy == "masked"
    assert rewrite_run.prompt_version == REWRITE_PROMPT_VERSION
    assert generate_run.prompt_version == GENERATE_PROMPT_VERSION
    assert rewrite_run.run_id == generate_run.run_id
    assert rewrite_run.tags == ("qa",)
    assert any("personalização" in message.content for message in rewrite_messages)
    assert any(message.content == "Quero visitar alguém." for message in rewrite_messages)
    assert embeddings.queries == [query_embedding_text("Horário de visita")]
    assert search.calls[0][0] == "Horário de visita"
    generated = "\n".join(message.content for message in generate_messages)
    assert UNTRUSTED_INTRO in generated
    assert "não confiável" in generated
    assert "11:00 às 20:00." in generated
    assert "personalização" not in generated


def test_open_circuit_returns_degraded_without_calling_the_generator() -> None:
    chat, embeddings, search = _parts(CircuitOpen("circuito aberto"))
    result = _run(chat, embeddings, search, "Qual é o horário?")
    assert result.outcome is Outcome.DEGRADED
    assert result.text == UNAVAILABLE
    assert chat.stream_calls == []
    assert embeddings.queries == []


def test_provider_failure_before_generation_is_error() -> None:
    chat, embeddings, search = _parts(ProviderUnavailable("indisponível"))
    result = _run(chat, embeddings, search, "Qual é o horário?")
    assert result.outcome is Outcome.ERROR
    assert result.text == UNAVAILABLE
    assert chat.stream_calls == []


def test_workflow_source_has_no_provider_keys() -> None:
    source = (_API / "app" / "workflows" / "qa.py").read_text(encoding="utf-8")
    assert "GEMINI_API_KEY" not in source
    assert "LANGSMITH_API_KEY" not in source


def test_ask_result_lists_outcome_citations_and_text() -> None:
    result = _run(
        *_parts(
            _classification("Horário de visita", "public_info", 0.9),
            hits=[_hit("11:00 às 20:00.")],
            tokens=["11:00 [1]."],
        ),
        "Qual é o horário?",
    )
    assert format_ask_result(result) == "answered\n1 | Visitas | Horário\n11:00 [1]."
    refused = _run(
        *_parts(_classification("dor", "medical_advice", 0.9)),
        "Estou com dor no peito",
    )
    assert format_ask_result(refused).splitlines()[0:2] == ["refused", "nenhuma"]


def test_workflow_streams_tokens_and_keeps_the_given_run_id() -> None:
    class Sink:
        def __init__(self) -> None:
            self.intents: list[str] = []
            self.tokens: list[str] = []

        async def classified(self, intent: str) -> None:
            self.intents.append(intent)

        async def token(self, text: str) -> None:
            self.tokens.append(text)

    sink = Sink()
    run_id = uuid4()
    chat, embeddings, search = _parts(
        _classification("Horário de visita", "public_info", 0.9),
        hits=[_hit("11:00 às 20:00.")],
        tokens=["11:00 ", "[1]."],
    )
    result = _run(chat, embeddings, search, "Qual é o horário?", events=sink, run_id=run_id)
    assert result.run_id == run_id
    assert result.outcome is Outcome.ANSWERED
    assert sink.intents == ["public_info"]
    assert sink.tokens == ["11:00 ", "[1]."]


def test_rewrite_and_generation_receive_only_the_history_window() -> None:
    """CA-1 da Etapa 12.3: o custo de uma pergunta não cresce com a conversa (seção 7.1)."""
    history: list[ConversationTurn] = []
    for number in range(1, 11):
        history.append(ConversationTurn(role="user", content=f"pergunta {number}"))
        history.append(ConversationTurn(role="assistant", content=f"resposta {number}"))
    chat, embeddings, search = _parts(
        _classification("Horário de visita", "public_info", 0.9),
        hits=[_hit("11:00 às 20:00.")],
        tokens=["11:00 [1]."],
    )
    result = _run(chat, embeddings, search, "E no domingo?", history=history)
    # A janela são as 6 últimas trocas, 12 mensagens. O `[1:-1]` tira a instrução de sistema
    # e a pergunta atual, que abrem e fecham a lista de mensagens.
    expected = [turn.content for turn in history[-12:]]
    rewrite = [message.content for message in chat.structured_calls[0][0]]
    generate = [message.content for message in chat.stream_calls[0][0]]
    assert result.outcome is Outcome.ANSWERED
    assert rewrite[1:-1] == expected
    assert generate[1:-1] == expected
    assert "pergunta 4" not in " ".join(rewrite + generate)


def test_cancelled_generation_leaves_the_partial_usage_in_the_tally() -> None:
    """Etapa 12.2: o uso já contado de uma resposta cancelada no meio chega a quem chamou."""
    # `pause_after=1` para o fluxo depois do primeiro token, e o teste cancela a tarefa ali.
    # O uso esperado é a reescrita (20, 3) mais um token (0, 5). O `stream_usage` só entraria
    # no fim do fluxo, que nunca chega.
    chat = FakeChatProvider(
        structured=_classification("Horário de visita", "public_info", 0.9),
        structured_usage=(20, 3),
        tokens=["11:00 ", "[1]."],
        token_usage=(0, 5),
        stream_usage=(40, 0),
        pause_after=1,
    )
    workflow = QaWorkflow(chat, _Embeddings(), _Search([_hit()]), minimum_similarity=0.5)
    tally = UsageTally()
    labels = {"model": "fake-chat", "direction": "output"}
    before = REGISTRY.get_sample_value("atrium_llm_tokens_total", labels) or 0.0

    async def cancel_midway() -> None:
        task = asyncio.create_task(
            workflow.run("Qual é o horário?", request_id="req-1", usage=tally)
        )
        await asyncio.wait_for(chat.paused.wait(), timeout=3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel_midway())
    after = REGISTRY.get_sample_value("atrium_llm_tokens_total", labels) or 0.0
    assert (tally.input_tokens, tally.output_tokens) == (20, 8)
    assert len(tally.runs) == 2
    assert after - before == 8


def test_tally_matches_the_tokens_of_a_complete_answer() -> None:
    # Entrada: 20 da reescrita e 40 do fim do fluxo. Saída: 3 da reescrita e 5 por token.
    chat = FakeChatProvider(
        structured=_classification("Horário de visita", "public_info", 0.9),
        structured_usage=(20, 3),
        tokens=["11:00 ", "[1]."],
        token_usage=(0, 5),
        stream_usage=(40, 0),
    )
    workflow = QaWorkflow(chat, _Embeddings(), _Search([_hit()]), minimum_similarity=0.5)
    tally = UsageTally()
    result = asyncio.run(workflow.run("Qual é o horário?", request_id="req-1", usage=tally))
    assert result.outcome is Outcome.ANSWERED
    assert (result.input_tokens, result.output_tokens) == (60, 13)
    assert (tally.input_tokens, tally.output_tokens) == (60, 13)


def test_medical_advice_is_classified_without_tokens() -> None:
    class Sink:
        def __init__(self) -> None:
            self.intents: list[str] = []
            self.tokens: list[str] = []

        async def classified(self, intent: str) -> None:
            self.intents.append(intent)

        async def token(self, text: str) -> None:
            self.tokens.append(text)

    sink = Sink()
    chat, embeddings, search = _parts(_classification("dor", "medical_advice", 0.9))
    result = _run(chat, embeddings, search, "Estou com dor no peito", events=sink)
    assert result.outcome is Outcome.REFUSED
    assert sink.intents == ["medical_advice"]
    assert sink.tokens == []
    assert chat.stream_calls == []


def test_ask_script_requires_gemini(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/unused")
    monkeypatch.setenv("APP_AI_ADAPTER", "fake")
    with pytest.raises(SystemExit):
        main(["Qual é o horário?"])
    assert "GEMINI_API_KEY" in capsys.readouterr().err


def _parts(
    structured: QuestionClassification | Exception,
    *,
    hits: list[RetrievedChunk] | None = None,
    tokens: Sequence[str] | Exception | None = None,
    structured_usage: tuple[int, int] = (0, 0),
    stream_usage: tuple[int, int] = (0, 0),
) -> tuple[FakeChatProvider, "_Embeddings", "_Search"]:
    """Os três falsos de um cenário: o chat, o embedding e a busca.

    `structured` é a classificação da reescrita ou o erro que ela levanta; `hits` são os chunks
    que a busca devolve, e `tokens`, o rascunho em fluxo.
    """
    return (
        FakeChatProvider(
            structured=structured,
            tokens=tokens,
            structured_usage=structured_usage,
            stream_usage=stream_usage,
        ),
        _Embeddings(),
        _Search(hits or []),
    )


def _run(
    chat: FakeChatProvider,
    embeddings: "_Embeddings",
    search: "_Search",
    question: str,
    *,
    history: Sequence[ConversationTurn] = (),
    visitor_type: str | None = None,
    minimum: float = 0.50,
    events: QaEventSink | None = None,
    run_id: UUID | None = None,
    tracer: "_RecordingTracer | None" = None,
) -> QaResult:
    """Monta o `QaWorkflow` com os falsos e roda uma pergunta com `asyncio.run`.

    O piso padrão é o `RETRIEVAL_MIN_SIMILARITY` de 0,50 da seção 7.1, e o `request_id` é fixo.
    """
    workflow = QaWorkflow(
        chat,
        embeddings,
        search,
        minimum_similarity=minimum,
        tracer=tracer,
    )

    async def execute() -> QaResult:
        return await workflow.run(
            question,
            history=history,
            visitor_type=visitor_type,
            request_id="req-1",
            run_id=run_id,
            events=events,
        )

    return asyncio.run(execute())


def _classification(
    question: str,
    intent: Literal["public_info", "medical_advice", "other"],
    confidence: float,
) -> QuestionClassification:
    """A saída estruturada da reescrita: pergunta autônoma, intenção e confiança."""
    return QuestionClassification(
        standalone_question=question,
        intent=intent,
        confidence=confidence,
    )


def _hit(content: str = "11:00 às 20:00.", *, similarity: float = 0.8) -> RetrievedChunk:
    """Um chunk do documento `02-visiting` com a similaridade pedida, acima do piso por padrão."""
    return RetrievedChunk(
        chunk_id=_CHUNK,
        document_slug="02-visiting",
        document_title="Visitas",
        heading="Horário",
        content=content,
        similarity=similarity,
    )


class _RecordingTracer:
    """Falso da porta `TraceRecorder`: guarda os `TraceEvent` em vez de enviá-los ao LangSmith."""

    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def record_many(self, events: Sequence[TraceEvent]) -> None:
        self.events.extend(events)


def _trace_text(events: Sequence[TraceEvent]) -> str:
    """Junta entradas, saídas e metadados de todos os eventos, para buscar um texto que vazou."""
    chunks: list[str] = []
    for event in events:
        chunks.append(str(event.inputs))
        chunks.append(str(event.outputs))
        chunks.append(str(event.metadata))
    return "\n".join(chunks)


class _Embeddings:
    """Falso da porta de embedding: guarda cada consulta e devolve um vetor fixo.

    `embed_documents` falha de propósito, porque a pergunta só embeda a consulta.
    """

    model_name = "fake-embedding"
    dimensions = 3

    def __init__(self) -> None:
        self.queries: list[str] = []

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise AssertionError(texts)

    async def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return [0.1, 0.2, 0.3]


class _Search:
    """Falso da porta `HybridSearch`: devolve `hits` e guarda a pergunta e o vetor pedidos."""

    def __init__(self, hits: list[RetrievedChunk]) -> None:
        self._hits = hits
        self.calls: list[tuple[str, list[float]]] = []

    async def search_by_vector(
        self,
        question: str,
        embedding: list[float],
    ) -> list[RetrievedChunk]:
        self.calls.append((question, list(embedding)))
        return self._hits
