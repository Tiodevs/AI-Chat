"""Pipeline de perguntas com guardas. Passos 1 a 7 da seção 7.1 do SDD."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.adapters.gemini_embedding import EmbeddingRequestError
from app.domain.embedding_text import query_embedding_text
from app.domain.errors import CircuitOpen, ProviderUnavailable
from app.domain.grounding import Citation, ContextBlock, check_grounding
from app.domain.outcomes import Outcome, gate_outcome
from app.domain.ranking import RESULT_LIMIT
from app.domain.retrieval import RetrievedChunk
from app.ports.chat import ChatProvider, Message, RunContext
from app.ports.embedding import EmbeddingProvider
from app.ports.search import HybridSearch
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


class QaWorkflow:
    def __init__(
        self,
        chat: ChatProvider,
        embeddings: EmbeddingProvider,
        search: HybridSearch,
        *,
        minimum_similarity: float,
    ) -> None:
        self._chat = chat
        self._embeddings = embeddings
        self._search = search
        self._minimum_similarity = minimum_similarity

    async def run(
        self,
        question: str,
        *,
        history: Sequence[ConversationTurn] = (),
        visitor_type: str | None = None,
        request_id: str,
        run_id: UUID | None = None,
        events: QaEventSink | None = None,
    ) -> QaResult:
        active_run_id = uuid4() if run_id is None else run_id
        rewrite = _run_context(
            run_id=active_run_id,
            request_id=request_id,
            prompt_version=REWRITE_PROMPT_VERSION,
            trace_policy="metadata_only",
            temperature=CLASSIFICATION_TEMPERATURE,
        )
        try:
            classification = await self._chat.complete_structured(
                _rewrite_messages(question, history, visitor_type),
                QuestionClassification,
                rewrite,
            )
        except CircuitOpen:
            return _failed(Outcome.DEGRADED, active_run_id, _tokens(rewrite))
        except ProviderUnavailable:
            return _failed(Outcome.ERROR, active_run_id, _tokens(rewrite))

        if events is not None:
            await events.classified(classification.intent)

        gated = gate_outcome(classification.intent, classification.confidence)
        standalone = classification.standalone_question.strip() or question
        if gated is not None:
            return _fixed(
                gated,
                active_run_id,
                _tokens(rewrite),
                model=self._chat.model_name,
                prompt_version=REWRITE_PROMPT_VERSION,
                intent=classification.intent,
                confidence=classification.confidence,
                standalone_question=standalone,
            )

        try:
            vector = await self._embeddings.embed_query(query_embedding_text(standalone))
            hits = await self._search.search_by_vector(standalone, vector)
        except EmbeddingRequestError:
            return _failed(
                Outcome.ERROR,
                active_run_id,
                _tokens(rewrite),
                model=self._chat.model_name,
                prompt_version=REWRITE_PROMPT_VERSION,
                intent=classification.intent,
                confidence=classification.confidence,
                standalone_question=standalone,
            )

        blocks = _blocks(hits, self._minimum_similarity)
        if not blocks:
            return _fixed(
                Outcome.ABSTAINED,
                active_run_id,
                _tokens(rewrite),
                model=self._chat.model_name,
                prompt_version=REWRITE_PROMPT_VERSION,
                intent=classification.intent,
                confidence=classification.confidence,
                standalone_question=standalone,
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
            return _failed(
                Outcome.DEGRADED,
                active_run_id,
                _tokens(rewrite, generate),
                model=self._chat.model_name,
                prompt_version=GENERATE_PROMPT_VERSION,
                intent=classification.intent,
                confidence=classification.confidence,
                standalone_question=standalone,
            )
        except ProviderUnavailable:
            return _failed(
                Outcome.ERROR,
                active_run_id,
                _tokens(rewrite, generate),
                model=self._chat.model_name,
                prompt_version=GENERATE_PROMPT_VERSION,
                intent=classification.intent,
                confidence=classification.confidence,
                standalone_question=standalone,
            )

        decision = check_grounding("".join(parts), blocks)
        usage = _tokens(rewrite, generate)
        if not decision.grounded:
            return _fixed(
                Outcome.GROUNDING_FAILED,
                active_run_id,
                usage,
                model=self._chat.model_name,
                prompt_version=GENERATE_PROMPT_VERSION,
                intent=classification.intent,
                confidence=classification.confidence,
                standalone_question=standalone,
            )
        return QaResult(
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


def _blocks(hits: Sequence[RetrievedChunk], minimum_similarity: float) -> list[ContextBlock]:
    eligible = [hit for hit in hits if hit.similarity >= minimum_similarity][:RESULT_LIMIT]
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
