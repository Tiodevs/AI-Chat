"""Pipeline de perguntas com guardas. Passos 1 a 7 da seção 7.1 do SDD.

Camada de workflow de IA (seção 6.2). Recebe pelo construtor as portas de chat, de embedding,
de busca e de rastro, e nunca abre sessão de banco nem importa FastAPI. O pipeline é Python
assíncrono comum: o LangChain fica atrás da porta de chat, no adaptador do Gemini. As regras
puras vêm de `app.domain` (janela do histórico, portão, fundamentação, políticas de rastro), e
os textos que o modelo lê e as respostas fixas vêm de `app.prompts.qa`.

Cada passo pode encerrar a pergunta com uma resposta fixa, e o gerador só roda quando todos os
anteriores deixaram passar (padrão "Pipeline com guardas" da seção 6.2). Os spans próprios são
os da seção 18.2, as métricas são as da seção 18.3 e o rastro segue a seção 18.4.

Quem usa: o `ConversationService` (`app.services.conversations`), pelo `AiRuntime` que
`app.core.container` monta uma vez por processo; o `QuestionService` (`app.services.question`);
e os scripts `ask` e `run_evals`.
"""

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app import __version__
from app.adapters.gemini_embedding import EmbeddingRequestError
from app.core.metrics import (
    LLM_DURATION,
    LLM_TOKENS,
    QA_FIRST_TOKEN,
    QA_OUTCOMES,
    QA_TOP_SIMILARITY,
)
from app.core.telemetry import traced_span
from app.domain.embedding_text import query_embedding_text
from app.domain.errors import CircuitOpen, ProviderUnavailable
from app.domain.grounding import Citation, ContextBlock, check_grounding
from app.domain.history import history_window
from app.domain.outcomes import Outcome, gate_outcome
from app.domain.ranking import RESULT_LIMIT
from app.domain.retrieval import RetrievedChunk
from app.domain.trace_policy import TraceMetadata, question_traces
from app.ports.chat import ChatProvider, Message, RunContext, UsageTally
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

# Seções 10.2 e 17: a classificação usa temperatura 0 e a resposta ao visitante, 0,2.
CLASSIFICATION_TEMPERATURE = 0.0
ANSWER_TEMPERATURE = 0.2


# Saída estruturada do passo 1 da seção 7.1. O adaptador manda este schema ao modelo e devolve
# a instância já validada pelo Pydantic. As descrições dos campos vêm de `app.prompts.qa` e vão
# ao modelo como parte do prompt, por isso entram no hash de `test_prompt_versions`. A classe
# não tem docstring de propósito: o Pydantic a poria como `description` do schema, e esse texto
# iria ao modelo fora da `PROMPT_VERSION`. `extra="ignore"` descarta campos que o modelo invente.
class QuestionClassification(BaseModel):
    model_config = ConfigDict(extra="ignore")

    standalone_question: str = Field(description=STANDALONE_DESCRIPTION)
    intent: Literal["public_info", "medical_advice", "other"] = Field(
        description=INTENT_DESCRIPTION
    )
    confidence: float = Field(description=CONFIDENCE_DESCRIPTION)


@dataclass(frozen=True, slots=True)
class ConversationTurn:
    """Uma mensagem do histórico da conversa, como o serviço a lê do banco.

    `role` segue a coluna `messages.role`. Uma pergunta médica anterior chega com o marcador
    `[health-related message not stored]` no lugar do texto, porque o histórico é lido do banco
    (seção 7.1). Satisfaz o protocolo `HistoryTurn` de `app.domain.history`.
    """

    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True, slots=True)
class QaResult:
    """O que o pipeline devolve ao serviço, qualquer que seja o desfecho.

    `text` é o rascunho aprovado ou a resposta fixa do desfecho (`fixed_text`, seção 10.1). Os
    tokens são a soma dos `RunContext` da reescrita e da geração. `model` e `prompt_version`
    ficam `None` quando a falha veio antes da classificação. `run_id` é o id do run raiz no
    LangSmith: o serviço passa o id da mensagem do assistente (seção 18.4). `chunks` são os
    blocos que foram ao gerador, preenchidos só no desfecho `answered`; o `run_evals` os usa
    para achar o documento de cada citação.
    """

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
    """Ganchos que o serviço recebe durante o pipeline.

    `classified` roda logo depois da reescrita e antes do portão. É ali que o serviço abre a
    primeira transação e grava a pergunta, já com o marcador quando é orientação médica
    (seção 7.1). Um erro levantado nesse gancho, como o reenvio do mesmo `client_message_id`,
    interrompe o pipeline. `token` recebe cada pedaço do rascunho assim que ele chega, para o
    serviço mandar o evento SSE `token`.
    """

    async def classified(self, intent: str) -> None: ...

    async def token(self, text: str) -> None: ...


def degraded_result(run_id: UUID | None = None) -> QaResult:
    """Resposta `degraded` sem passar pelo pipeline, para o orçamento estourado (seção 7.1).

    Sai sem tokens e sem modelo. O serviço a usa antes de chamar `run`, por isso ela não entra
    em `atrium_qa_outcomes`.
    """
    return _plain(Outcome.DEGRADED, run_id)


def error_result(run_id: UUID | None = None) -> QaResult:
    """Resposta `error` que o serviço monta quando `run` levantou uma exceção inesperada.

    O texto é o de indisponibilidade (seção 10.1). Como não passa por `run`, também fica fora
    de `atrium_qa_outcomes`.
    """
    return _plain(Outcome.ERROR, run_id)


def _plain(outcome: Outcome, run_id: UUID | None) -> QaResult:
    """Um `QaResult` só com o desfecho e o texto fixo dele. Sem `run_id`, nasce um novo."""
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
    """O que o `finally` de `run` precisa para métricas e rastro, mesmo num fim antecipado.

    `_execute` preenche os campos à medida que avança. `result` fica `None` quando o pipeline
    foi cancelado ou quebrou no meio; aí só os tokens já cobrados entram na métrica.
    """

    result: QaResult | None = None
    classified: bool = False
    intent: str | None = None
    confidence: float | None = None
    standalone: str | None = None
    chunks: list[RetrievedChunk] = field(default_factory=list)


class QaWorkflow:
    """Os passos 1 a 7 da seção 7.1, com uma guarda em cada um.

    Nasce uma vez por processo, no `AiRuntime`, e atende pedidos simultâneos: o estado de cada
    pergunta vive nas variáveis locais de `run`, nunca no objeto. `search` é a busca híbrida
    da seção 8.4 (o `RetrievalService`, que abre a própria sessão de banco).
    `minimum_similarity` é o `RETRIEVAL_MIN_SIMILARITY`. Sem `tracer`, o `NullTracer` descarta
    os rastros, como nos scripts `ask` e `run_evals`.
    """

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
        usage: UsageTally | None = None,
    ) -> QaResult:
        """Responde a uma pergunta e devolve o `QaResult` com o desfecho.

        Reescrita e geração recebem só a janela do histórico (seção 7.1 do SDD).

        1. Corta o histórico na janela da seção 7.1 (`history_window`).
        2. Registra o `RunContext` da reescrita no `UsageTally`.
        3. Executa os passos em `_execute`.
        4. No `finally`, conta o desfecho e os tokens nas métricas e grava o rastro. Se o
           pipeline foi cancelado ou quebrou, conta só os tokens e não grava rastro.

        `usage` recebe cada chamada ao modelo, para quem chama ler o uso parcial. Ele vale
        também para uma resposta cancelada, porque o adaptador soma os tokens a cada pedaço
        do fluxo (seções 6.4 e 7.1). `run_id` vira o id do run raiz no LangSmith;
        sem ele, nasce um novo. `visitor_type` entra na reescrita quando há consentimento de
        personalização, mas o `ConversationService` hoje passa sempre `None`; a Etapa 13.4
        decide entre implementar e tirar da seção 7.1. `trace_metadata` traz os metadados da
        seção 18.4.

        Falhas conhecidas do provedor viram desfecho: `CircuitOpen` vira `degraded`, e
        `ProviderUnavailable` e `EmbeddingRequestError` viram `error`. Outras exceções sobem
        para o serviço, como um erro de rede do embedding (Etapa 13.2), um erro do banco na
        busca, o `DuplicateClientMessage` do gancho `classified` e o `asyncio.CancelledError`
        de um visitante que fechou o fluxo.
        """
        observed = _Observed()
        # 1.
        window = history_window(history)
        tally = UsageTally() if usage is None else usage
        active_run_id = uuid4() if run_id is None else run_id
        # 2. Política `metadata_only`: a pergunta original pode ter dado de saúde (seção 18.4).
        rewrite = tally.track(
            _run_context(
                run_id=active_run_id,
                request_id=request_id,
                prompt_version=REWRITE_PROMPT_VERSION,
                trace_policy="metadata_only",
                temperature=CLASSIFICATION_TEMPERATURE,
            )
        )
        try:
            # 3.
            return await self._execute(
                question,
                history=window,
                visitor_type=visitor_type,
                request_id=request_id,
                events=events,
                observed=observed,
                active_run_id=active_run_id,
                rewrite=rewrite,
                tally=tally,
            )
        finally:
            # 4. Roda também no cancelamento, que chega como `CancelledError` no `await`.
            if observed.result is not None:
                _count_outcome(observed.result, self._chat.model_name)
                self._record(
                    observed,
                    rewrite_tokens=(rewrite.input_tokens, rewrite.output_tokens),
                    request_id=request_id,
                    trace_metadata=trace_metadata,
                )
            else:
                # Cancelada ou quebrada no meio: os tokens já cobrados entram na métrica.
                _count_tokens(self._chat.model_name, tally.input_tokens, tally.output_tokens)

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
        tally: UsageTally,
    ) -> QaResult:
        """Os passos da seção 7.1. Todo `return` passa por `_keep`, que guarda o resultado.

        1. Reescrever e classificar, numa chamada de saída estruturada (`qa.rewrite`).
        2. Avisar o serviço (`events.classified`) e aplicar o portão (`gate_outcome`).
        3. Embedar a pergunta autônoma e recuperar (`qa.embed_query` e `qa.retrieve`).
        4. Abster-se quando nenhum candidato alcança o piso de similaridade.
        5. Gerar em fluxo (`qa.generate`), repassando cada token ao serviço.
        6. Fundamentar o rascunho (`qa.ground`) e montar o resultado.
        """
        # 1. Reescrever. Uma chamada só devolve a pergunta autônoma, a intenção e a confiança.
        try:
            with traced_span(
                "qa.rewrite",
                run_id=active_run_id,
                model=self._chat.model_name,
                prompt_version=REWRITE_PROMPT_VERSION,
            ) as rewrite_span:
                started = time.perf_counter()
                classification = await self._chat.complete_structured(
                    _rewrite_messages(question, history, visitor_type),
                    QuestionClassification,
                    rewrite,
                )
                LLM_DURATION.labels(operation="rewrite").observe(time.perf_counter() - started)
                rewrite_span.set(intent=classification.intent)
        # `CircuitOpen` herda de `ProviderUnavailable`, então precisa vir primeiro. Com o
        # circuito aberto, a pergunta degrada sem chamar o gerador (seção 7.1).
        except CircuitOpen:
            return _keep(observed, _failed(Outcome.DEGRADED, active_run_id, _tokens(rewrite)))
        # Falha com o circuito fechado: desfecho `error`, com o texto de indisponibilidade.
        except ProviderUnavailable:
            return _keep(observed, _failed(Outcome.ERROR, active_run_id, _tokens(rewrite)))

        observed.classified = True
        observed.intent = classification.intent
        observed.confidence = classification.confidence
        # Uma reescrita vazia não pode virar uma busca vazia: vale a pergunta original.
        standalone = classification.standalone_question.strip() or question
        observed.standalone = standalone
        # 2. A classificação termina antes da primeira transação: o serviço grava a pergunta
        # aqui, com o marcador quando a intenção é `medical_advice` (seção 7.1).
        if events is not None:
            await events.classified(classification.intent)

        # Portão: só `public_info` com confiança de pelo menos 0,6 segue. O resto recebe a
        # resposta fixa, sem recuperação e sem gerador (seção 7.1, passo 2).
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

        # 3. O texto embedado leva o prefixo da seção 8.3. A busca recebe a pergunta autônoma,
        # para a parte de palavras-chave, e o vetor, para a parte vetorial (seção 8.4).
        try:
            with traced_span(
                "qa.embed_query",
                run_id=active_run_id,
                model=self._embeddings.model_name,
                dimensions=self._embeddings.dimensions,
            ):
                vector = await self._embeddings.embed_query(query_embedding_text(standalone))
            with traced_span("qa.retrieve", run_id=active_run_id) as retrieve_span:
                hits = await self._search.search_by_vector(standalone, vector)
                # A busca já aplica o piso, então `top` só vê candidatos acima dele, e uma
                # abstenção não alimenta o histograma. A Etapa 13.5 mede antes do piso.
                top = max((hit.similarity for hit in hits), default=None)
                retrieve_span.set(candidate_count=len(hits), top_similarity=top)
                if top is not None:
                    QA_TOP_SIMILARITY.observe(top)
        # O erro vem de `app.adapters`, que um workflow não deveria importar. A Etapa 13.2 o
        # leva para a porta e mapeia os erros de rede do `httpx`, que hoje escapam daqui.
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

        # 4. O piso e o limite de 6 blocos valem de novo aqui, para a guarda não depender da
        # implementação da porta. Sem bloco, abstenção sem chamar o gerador (seção 7.1).
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

        # 5. O `RunContext` da geração entra no `UsageTally` antes do fluxo, para quem chama
        # ler os tokens parciais de uma resposta cancelada (seção 6.4). Política `masked` e
        # temperatura 0,2 (seções 18.4 e 10.2).
        generate = tally.track(
            _run_context(
                run_id=active_run_id,
                request_id=request_id,
                prompt_version=GENERATE_PROMPT_VERSION,
                trace_policy="masked",
                temperature=ANSWER_TEMPERATURE,
            )
        )
        parts: list[str] = []
        try:
            with traced_span(
                "qa.generate",
                run_id=active_run_id,
                model=self._chat.model_name,
                prompt_version=GENERATE_PROMPT_VERSION,
            ) as generate_span:
                started = time.perf_counter()
                try:
                    async for token in self._chat.stream(
                        _generate_messages(question, history, blocks),
                        generate,
                    ):
                        # Primeiro pedaço: alimenta `atrium_qa_first_token_seconds` (seção 18.3).
                        if not parts:
                            QA_FIRST_TOKEN.observe(time.perf_counter() - started)
                        # O token vai ao visitante antes da fundamentação. Se ela reprovar
                        # depois, o serviço manda o evento `replace` (seção 7.1).
                        if events is not None:
                            await events.token(token)
                        parts.append(token)
                finally:
                    # Roda também na falha e no cancelamento, para o span levar o uso parcial.
                    LLM_DURATION.labels(operation="generate").observe(time.perf_counter() - started)
                    generate_span.set(
                        input_tokens=generate.input_tokens,
                        output_tokens=generate.output_tokens,
                    )
        # O circuito pode ter aberto entre a reescrita e a geração, por falhas de outros pedidos.
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

        # 6. Fundamentar: funções puras do domínio conferem as citações `[n]` e os telefones
        # do rascunho contra os blocos recuperados (seção 7.1, passo 7).
        with traced_span("qa.ground", run_id=active_run_id) as ground_span:
            decision = check_grounding("".join(parts), blocks)
            ground_span.set(outcome="grounded" if decision.grounded else "grounding_failed")
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
        """Grava o rastro do LangSmith com a política da seção 18.4 e do ADR-006.

        `question_traces` monta a raiz `qa` e, se houve classificação, o filho `qa.rewrite`,
        só com metadados. Apenas `public_info` leva conteúdo: a pergunta autônoma, os blocos
        que foram ao gerador, a resposta e as citações, depois do anonimizador (`masked`).
        Orientação médica, fora de tema e falhas antes da classificação levam só metadados. O
        anonimizador não marca nomes próprios; a Etapa 15.3 decide entre redação extra e
        `metadata_only` na geração. O tracer do LangSmith registra as próprias falhas no log e
        não as levanta.
        """
        result = observed.result
        if result is None:
            return
        public = observed.intent == "public_info"
        by_chunk = {chunk.chunk_id: chunk for chunk in observed.chunks}
        # A citação do domínio não tem o slug: ele vem do chunk recuperado com o mesmo id.
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
                # Sem os metadados do serviço, o rastro sai marcado como `local`.
                trace=trace_metadata or TraceMetadata(environment="local", app_version=__version__),
            )
        )


def _rewrite_messages(
    question: str,
    history: Sequence[ConversationTurn],
    visitor_type: str | None,
) -> list[Message]:
    """Mensagens da reescrita: as regras, a nota do tipo de visitante, a janela e a pergunta.

    A nota do `visitor_type` só entra quando ele vem preenchido, o que pressupõe o
    consentimento de personalização (seção 7.1, passo 1).
    """
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
    """Mensagens da geração: as regras, a janela e a pergunta seguida dos blocos numerados.

    A geração recebe a pergunta original e a janela do histórico; a pergunta autônoma da
    reescrita serve à busca e ao rastro. `untrusted_block` embrulha cada bloco como dado não
    confiável (seção 10.2). O conteúdo entra sem tratamento, então um documento com a tag de
    fechamento encerra o bloco antes da hora; a Etapa 15.3 neutraliza a tag. O
    `DemoChatProvider` lê esses blocos por expressão regular, então o formato é contrato com ele.
    """
    rendered = "\n\n".join(
        untrusted_block(block.index, block.heading or NO_SECTION, block.content) for block in blocks
    )
    messages = [Message(role="system", content=GENERATE_INSTRUCTIONS)]
    messages.extend(_history(history))
    messages.append(Message(role="user", content=f"{question}\n\n{UNTRUSTED_INTRO}\n\n{rendered}"))
    return messages


def _history(history: Sequence[ConversationTurn]) -> list[Message]:
    """Os turnos do histórico como mensagens da porta de chat, com o mesmo papel."""
    return [Message(role=turn.role, content=turn.content) for turn in history]


def _count_outcome(result: QaResult, model: str) -> None:
    """Conta o desfecho em `atrium_qa_outcomes` e os tokens em `atrium_llm_tokens` (seção 18.3)."""
    QA_OUTCOMES.labels(outcome=result.outcome.value).inc()
    _count_tokens(model, result.input_tokens, result.output_tokens)


def _count_tokens(model: str, input_tokens: int, output_tokens: int) -> None:
    """Soma os tokens em `atrium_llm_tokens`, com o modelo de chat no rótulo `model`."""
    LLM_TOKENS.labels(model=model, direction="input").inc(input_tokens)
    LLM_TOKENS.labels(model=model, direction="output").inc(output_tokens)


def _keep(observed: _Observed, result: QaResult) -> QaResult:
    """Guarda o resultado em `observed` e o devolve, para o `finally` de `run` saber dele."""
    observed.result = result
    return result


def _eligible(hits: Sequence[RetrievedChunk], minimum_similarity: float) -> list[RetrievedChunk]:
    """Os candidatos que alcançam o piso, até `RESULT_LIMIT` (6, seção 8.4), na ordem da busca."""
    return [hit for hit in hits if hit.similarity >= minimum_similarity][:RESULT_LIMIT]


def _blocks(hits: Sequence[RetrievedChunk], minimum_similarity: float) -> list[ContextBlock]:
    """Os candidatos elegíveis como blocos de contexto, numerados a partir de 1.

    O número é o `[n]` que o modelo cita e que a fundamentação confere (seção 7.1, passo 7).
    """
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
    """O `RunContext` de uma chamada da pergunta, com a tag `qa` (seção 17).

    Os adaptadores de hoje leem dele só a temperatura e somam nele os tokens. A política
    escrita aqui vale para o rastro explícito de `_record`, não para a chamada ao modelo.
    """
    return RunContext(
        run_id=run_id,
        request_id=request_id,
        prompt_version=prompt_version,
        trace_policy=trace_policy,
        tags=("qa",),
        temperature=temperature,
    )


def _tokens(*runs: RunContext) -> tuple[int, int]:
    """Soma os tokens de entrada e de saída de vários `RunContext`."""
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
    """Resposta fixa depois da classificação: portão, abstenção ou fundamentação reprovada.

    Os campos da classificação são obrigatórios, porque nesse ponto eles já existem.
    """
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
    """Resposta fixa de uma falha do provedor (`degraded` ou `error`).

    Os campos da classificação são opcionais, porque a falha pode vir antes dela.
    """
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
