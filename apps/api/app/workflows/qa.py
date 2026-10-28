"""Pipeline de perguntas com guardas. Passos 1 a 7 da seção 7.1 do SDD."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app import __version__
from app.adapters.gemini_embedding import EmbeddingRequestError
from app.domain.embedding_text import query_embedding_text
from app.domain.errors import CircuitOpen, ProviderUnavailable
from app.domain.grounding import Citation, ContextBlock, check_grounding
from app.domain.outcomes import Outcome, gate_outcome
from app.domain.ranking import RESULT_LIMIT
from app.domain.retrieval import RetrievedChunk
from app.domain.trace_policy import TraceMetadata, question_traces
from app.ports.chat import ChatProvider, Message, RunContext
from app.ports.embedding import EmbeddingProvider
from app.ports.search import HybridSearch
from app.ports.tracing import NullTracer, TraceRecorder
from app.prompts.qa import (
    CONFIDENCE_DESCRIPTION,
    GENERATE_INSTRUCTIONS,
    GENERATE_PROMPT_VERSION,
    INTENT_DESCRIPTION,
    NO_SECTION,
    REWRITE_INSTRUCTIONS,
    REWRITE_PROMPT_VERSION,
    STANDALONE_DESCRIPTION,
    UNTRUSTED_INTRO,
    fixed_text,
    untrusted_block,
    visitor_type_note,
)

CLASSIFICATION_TEMPERATURE = 0.0
ANSWER_TEMPERATURE = 0.2


class QuestionClassification(BaseModel):
    model_config = ConfigDict(extra="ignore")

    standalone_question: str = Field(description=STANDALONE_DESCRIPTION)
    intent: Literal["public_info", "medical_advice", "other"] = Field(
        description=INTENT_DESCRIPTION
    )
    confidence: float = Field(description=CONFIDENCE_DESCRIPTION)


@dataclass(frozen=True, slots=True)
class ConversationTurn:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True, slots=True)
class QaResult:
    outcome: Outcome
    text: str
    citations: tuple[Citation, ...]
    input_tokens: int
    output_tokens: int
    model: str | None
    prompt_version: str | None
    intent: str | None
    confidence: float | None
    standalone_question: str | None
    run_id: UUID
    chunks: tuple[RetrievedChunk, ...] = ()


class QaEventSink(Protocol):
    async def classified(self, intent: str) -> None: ...

    async def token(self, text: str) -> None: ...


def degraded_result(run_id: UUID | None = None) -> QaResult:
    return _plain(Outcome.DEGRADED, run_id)


def error_result(run_id: UUID | None = None) -> QaResult:
    return _plain(Outcome.ERROR, run_id)


def _plain(outcome: Outcome, run_id: UUID | None) -> QaResult:
    return QaResult(
        outcome=outcome,
        text=fixed_text(outcome),
        citations=(),
        input_tokens=0,
        output_tokens=0,
        model=None,
        prompt_version=None,
        intent=None,
        confidence=None,
        standalone_question=None,
        run_id=run_id or uuid4(),
    )


@dataclass
class _Observed:
    result: QaResult | None = None
    classified: bool = False
    intent: str | None = None
    confidence: float | None = None
    standalone: str | None = None
    chunks: list[RetrievedChunk] = field(default_factory=list)


class QaWorkflow:
    def __init__(
        self,
        chat: ChatProvider,
        embeddings: EmbeddingProvider,
        search: HybridSearch,
        *,
        minimum_similarity: float,
        tracer: TraceRecorder | None = None,
    ) -> None:
        self._chat = chat
        self._embeddings = embeddings
        self._search = search
        self._minimum_similarity = minimum_similarity
        self._tracer = tracer or NullTracer()

    async def run(
        self,
        question: str,
        *,
        history: Sequence[ConversationTurn] = (),
        visitor_type: str | None = None,
        request_id: str,
        run_id: UUID | None = None,
        events: QaEventSink | None = None,
        trace_metadata: TraceMetadata | None = None,
    ) -> QaResult:
        observed = _Observed()
        active_run_id = uuid4() if run_id is None else run_id
        rewrite = _run_context(
            run_id=active_run_id,
            request_id=request_id,
            prompt_version=REWRITE_PROMPT_VERSION,
            trace_policy="metadata_only",
            temperature=CLASSIFICATION_TEMPERATURE,
        )
        try:
            return await self._execute(
                question,
                history=history,
                visitor_type=visitor_type,
                request_id=request_id,
                events=events,
                observed=observed,
                active_run_id=active_run_id,
                rewrite=rewrite,
            )
        finally:
            if observed.result is not None:
                self._record(
                    observed,
                    rewrite_tokens=(rewrite.input_tokens, rewrite.output_tokens),
                    request_id=request_id,
                    trace_metadata=trace_metadata,
                )

    async def _execute(
        self,
        question: str,
        *,
        history: Sequence[ConversationTurn],
        visitor_type: str | None,
        request_id: str,
        events: QaEventSink | None,
        observed: _Observed,
        active_run_id: UUID,
        rewrite: RunContext,
    ) -> QaResult:
        try:
            classification = await self._chat.complete_structured(
                _rewrite_messages(question, history, visitor_type),
                QuestionClassification,
                rewrite,
            )
        except CircuitOpen:
            return _keep(observed, _failed(Outcome.DEGRADED, active_run_id, _tokens(rewrite)))
        except ProviderUnavailable:
            return _keep(observed, _failed(Outcome.ERROR, active_run_id, _tokens(rewrite)))

        observed.classified = True
        observed.intent = classification.intent
        observed.confidence = classification.confidence
        standalone = classification.standalone_question.strip() or question
        observed.standalone = standalone
        if events is not None:
            await events.classified(classification.intent)

        gated = gate_outcome(classification.intent, classification.confidence)
        if gated is not None:
            return _keep(
                observed,
                _fixed(
                    gated,
                    active_run_id,
                    _tokens(rewrite),
                    model=self._chat.model_name,
                    prompt_version=REWRITE_PROMPT_VERSION,
                    intent=classification.intent,
                    confidence=classification.confidence,
                    standalone_question=standalone,
                ),
            )

        try:
            vector = await self._embeddings.embed_query(query_embedding_text(standalone))
            hits = await self._search.search_by_vector(standalone, vector)
        except EmbeddingRequestError:
            return _keep(
                observed,
                _failed(
                    Outcome.ERROR,
                    active_run_id,
                    _tokens(rewrite),
                    model=self._chat.model_name,
                    prompt_version=REWRITE_PROMPT_VERSION,
                    intent=classification.intent,
                    confidence=classification.confidence,
                    standalone_question=standalone,
                ),
            )

        observed.chunks = _eligible(hits, self._minimum_similarity)
        blocks = _blocks(hits, self._minimum_similarity)
        if not blocks:
            return _keep(
                observed,
                _fixed(
                    Outcome.ABSTAINED,
                    active_run_id,
                    _tokens(rewrite),
                    model=self._chat.model_name,
                    prompt_version=REWRITE_PROMPT_VERSION,
                    intent=classification.intent,
                    confidence=classification.confidence,
                    standalone_question=standalone,
                ),
            )

        generate = _run_context(
            run_id=active_run_id,
            request_id=request_id,
            prompt_version=GENERATE_PROMPT_VERSION,
            trace_policy="masked",
            temperature=ANSWER_TEMPERATURE,
        )
        parts: list[str] = []
        try:
            async for token in self._chat.stream(
                _generate_messages(question, history, blocks),
                generate,
            ):
                if events is not None:
                    await events.token(token)
                parts.append(token)
        except CircuitOpen:
            return _keep(
                observed,
                _failed(
                    Outcome.DEGRADED,
                    active_run_id,
                    _tokens(rewrite, generate),
                    model=self._chat.model_name,
                    prompt_version=GENERATE_PROMPT_VERSION,
                    intent=classification.intent,
                    confidence=classification.confidence,
                    standalone_question=standalone,
                ),
            )
        except ProviderUnavailable:
            return _keep(
                observed,
                _failed(
                    Outcome.ERROR,
                    active_run_id,
                    _tokens(rewrite, generate),
                    model=self._chat.model_name,
                    prompt_version=GENERATE_PROMPT_VERSION,
                    intent=classification.intent,
                    confidence=classification.confidence,
                    standalone_question=standalone,
                ),
            )

        decision = check_grounding("".join(parts), blocks)
        usage = _tokens(rewrite, generate)
        if not decision.grounded:
            return _keep(
                observed,
                _fixed(
                    Outcome.GROUNDING_FAILED,
                    active_run_id,
                    usage,
                    model=self._chat.model_name,
                    prompt_version=GENERATE_PROMPT_VERSION,
                    intent=classification.intent,
                    confidence=classification.confidence,
                    standalone_question=standalone,
                ),
            )
        return _keep(
            observed,
            QaResult(
                outcome=Outcome.ANSWERED,
                text="".join(parts),
                citations=decision.citations,
                input_tokens=usage[0],
                output_tokens=usage[1],
                model=self._chat.model_name,
                prompt_version=GENERATE_PROMPT_VERSION,
                intent=classification.intent,
                confidence=classification.confidence,
                standalone_question=standalone,
                run_id=active_run_id,
                chunks=tuple(observed.chunks),
            ),
        )

    def _record(
        self,
        observed: _Observed,
        *,
        rewrite_tokens: tuple[int, int],
        request_id: str,
        trace_metadata: TraceMetadata | None,
    ) -> None:
        result = observed.result
        if result is None:
            return
        public = observed.intent == "public_info"
        by_chunk = {chunk.chunk_id: chunk for chunk in observed.chunks}
        citations = [
            {
                "index": citation.index,
                "document_slug": by_chunk[citation.chunk_id].document_slug
                if citation.chunk_id in by_chunk
                else "",
                "document_title": citation.document_title,
                "heading": citation.heading,
            }
            for citation in result.citations
        ]
        chunks = [
            {
                "document_slug": chunk.document_slug,
                "document_title": chunk.document_title,
                "heading": chunk.heading,
                "content": chunk.content,
            }
            for chunk in observed.chunks
        ]
        self._tracer.record_many(
            question_traces(
                run_id=result.run_id,
                intent=observed.intent,
                confidence=observed.confidence,
                outcome=result.outcome.value,
                standalone_question=observed.standalone if public else None,
                chunks=chunks if public else (),
                answer=result.text if public else "",
                citations=citations if public else (),
                prompt_version=result.prompt_version,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                classified=observed.classified,
                rewrite_prompt_version=REWRITE_PROMPT_VERSION,
                rewrite_input_tokens=rewrite_tokens[0],
                rewrite_output_tokens=rewrite_tokens[1],
                request_id=request_id,
                trace=trace_metadata or TraceMetadata(environment="local", app_version=__version__),
            )
        )


def _rewrite_messages(
    question: str,
    history: Sequence[ConversationTurn],
    visitor_type: str | None,
) -> list[Message]:
    messages = [Message(role="system", content=REWRITE_INSTRUCTIONS)]
    if visitor_type and visitor_type.strip():
        messages.append(Message(role="system", content=visitor_type_note(visitor_type.strip())))
    messages.extend(_history(history))
    messages.append(Message(role="user", content=question))
    return messages


def _generate_messages(
    question: str,
    history: Sequence[ConversationTurn],
    blocks: Sequence[ContextBlock],
) -> list[Message]:
    rendered = "\n\n".join(
        untrusted_block(block.index, block.heading or NO_SECTION, block.content) for block in blocks
    )
    messages = [Message(role="system", content=GENERATE_INSTRUCTIONS)]
    messages.extend(_history(history))
    messages.append(Message(role="user", content=f"{question}\n\n{UNTRUSTED_INTRO}\n\n{rendered}"))
    return messages


def _history(history: Sequence[ConversationTurn]) -> list[Message]:
    return [Message(role=turn.role, content=turn.content) for turn in history]


def _keep(observed: _Observed, result: QaResult) -> QaResult:
    observed.result = result
    return result


def _eligible(hits: Sequence[RetrievedChunk], minimum_similarity: float) -> list[RetrievedChunk]:
    return [hit for hit in hits if hit.similarity >= minimum_similarity][:RESULT_LIMIT]


def _blocks(hits: Sequence[RetrievedChunk], minimum_similarity: float) -> list[ContextBlock]:
    eligible = _eligible(hits, minimum_similarity)
    return [
        ContextBlock(
            index=index,
            chunk_id=hit.chunk_id,
            document_title=hit.document_title,
            heading=hit.heading,
            content=hit.content,
        )
        for index, hit in enumerate(eligible, start=1)
    ]


def _run_context(
    *,
    run_id: UUID,
    request_id: str,
    prompt_version: str,
    trace_policy: Literal["full", "masked", "metadata_only"],
    temperature: float,
) -> RunContext:
    return RunContext(
        run_id=run_id,
        request_id=request_id,
        prompt_version=prompt_version,
        trace_policy=trace_policy,
        tags=("qa",),
        temperature=temperature,
    )


def _tokens(*runs: RunContext) -> tuple[int, int]:
    return (
        sum(run.input_tokens for run in runs),
        sum(run.output_tokens for run in runs),
    )


def _fixed(
    outcome: Outcome,
    run_id: UUID,
    tokens: tuple[int, int],
    *,
    model: str,
    prompt_version: str,
    intent: str,
    confidence: float,
    standalone_question: str,
) -> QaResult:
    return QaResult(
        outcome=outcome,
        text=fixed_text(outcome),
        citations=(),
        input_tokens=tokens[0],
        output_tokens=tokens[1],
        model=model,
        prompt_version=prompt_version,
        intent=intent,
        confidence=confidence,
        standalone_question=standalone_question,
        run_id=run_id,
    )


def _failed(
    outcome: Outcome,
    run_id: UUID,
    tokens: tuple[int, int],
    *,
    model: str | None = None,
    prompt_version: str | None = None,
    intent: str | None = None,
    confidence: float | None = None,
    standalone_question: str | None = None,
) -> QaResult:
    return QaResult(
        outcome=outcome,
        text=fixed_text(outcome),
        citations=(),
        input_tokens=tokens[0],
        output_tokens=tokens[1],
        model=model,
        prompt_version=prompt_version,
        intent=intent,
        confidence=confidence,
        standalone_question=standalone_question,
        run_id=run_id,
    )
