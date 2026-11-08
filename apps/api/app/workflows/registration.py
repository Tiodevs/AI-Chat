"""Grafo do cadastro: extract, decide_next e phrase. Sem checkpointer. Seção 7.2.

Camada de workflow de IA (seção 6.2). O LangGraph só orquestra três nós em linha; quem decide o
próximo passo é a máquina de estados pura de `app.domain.registration` (ADR-003). O modelo só
extrai campos por uma ferramenta com lista de permissão e escreve a frase do turno. Ele não
conclui a conta, não define `role`, não registra consentimento e não vê a senha (seção 10.2).

Quem usa: `RegistrationService.message` (`app.services.registration`), pelo `AiRuntime` de
`app.core.container`, que compila o grafo uma vez por processo. Usa a porta de chat, a porta de
rastro, as regras de `app.domain.fields` e os textos de `app.prompts.registration`.
"""

from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from typing import Any, TypedDict
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.core.metrics import REGISTRATION_EVENTS
from app.core.telemetry import traced_span
from app.domain.errors import ProviderUnavailable
from app.domain.fields import (
    SET_FIELDS_TOOL_NAME,
    ToolRead,
    read_tool_arguments,
    rejected_tool,
    set_fields_parameters,
)
from app.domain.registration import (
    Machine,
    Step,
    apply_collected,
    decide_next,
    public_fields,
)
from app.domain.trace_policy import registration_event_from_record
from app.ports.chat import ChatProvider, Message, RunContext, Tool
from app.ports.tracing import NullTracer, TraceRecorder
from app.prompts.registration import (
    EXTRACT_INSTRUCTIONS,
    EXTRACT_PROMPT_VERSION,
    PHRASE_INSTRUCTIONS,
    PHRASE_PROMPT_VERSION,
    PHRASE_TEXT_DESCRIPTION,
    REGISTRATION_UNAVAILABLE,
    SET_FIELDS_DESCRIPTION,
    TOOL_PROPERTY_DESCRIPTIONS,
    issue_reply,
    prompt_for,
    review_prompt,
)

# Seção 10.2: a extração usa temperatura 0. A frase é resposta ao visitante, então usa 0,2.
EXTRACT_TEMPERATURE = 0.0
PHRASE_TEMPERATURE = 0.2
# Uma frase do modelo vazia ou maior que isto é trocada pela pergunta modelo do passo. A seção
# 7.2 pede uma resposta curta e não fixa o número.
MAX_PHRASE_CHARS = 500

# A consulta de e-mail já usado que o serviço injeta a cada turno. O workflow recebe só a
# função e não sabe que ela abre uma sessão de banco (seção 6.2).
EmailTaken = Callable[[str], Awaitable[bool]]


# Saída estruturada do nó `phrase`: um texto curto em português. A classe não tem docstring de
# propósito: o Pydantic a poria como `description` do schema enviado ao modelo, fora da
# `PROMPT_VERSION`. A descrição do campo vem de `app.prompts.registration` e entra no hash.
class PhraseText(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str = Field(description=PHRASE_TEXT_DESCRIPTION)


class GraphState(TypedDict, total=False):
    """O estado que passa de nó em nó durante um turno.

    No LangGraph, cada nó recebe o estado e devolve só as chaves que mudou. Sem redutor
    declarado, o valor novo substitui o antigo, e por isso os nós somam os tokens à mão. O
    estado nasce em `turn` e acaba com o `ainvoke`: sem checkpointer, nada fica guardado entre
    turnos, e o serviço persiste a `Machine` no PostgreSQL (seção 7.2).

    `user_text` é a mensagem do visitante; `prompt`, a frase do turno; `accepted_names`, os
    nomes dos campos aceitos na extração; `run_id`, o id do rastro do turno, em texto.
    """

    machine: Machine
    user_text: str
    request_id: str
    prompt: str
    input_tokens: int
    output_tokens: int
    accepted_names: list[str]
    run_id: str


@dataclass(frozen=True, slots=True)
class TurnResult:
    """O que um turno devolve ao serviço.

    `machine` é a máquina nova, que o serviço grava; `prompt`, a frase que vai à transcrição e
    à tela; `accepted_names`, só os nomes dos campos aceitos, a mesma lista do rastro. Os
    tokens somam a extração e a frase, para o serviço gravar em `token_usage_days` (seção 7.2).
    """

    machine: Machine
    prompt: str
    accepted_names: tuple[str, ...]
    input_tokens: int
    output_tokens: int


async def _email_is_free(_email: str) -> bool:
    """Consulta padrão, sem banco: nenhum e-mail conta como já usado."""
    return False


# O grafo compilado é compartilhado entre pedidos simultâneos. O `ContextVar` entrega ao nó
# `extract` a consulta de e-mail do pedido, sem pô-la no estado do grafo nem no workflow: cada
# tarefa do asyncio enxerga a própria cópia do contexto, então um pedido não vê a de outro.
_email_taken: ContextVar[EmailTaken] = ContextVar(
    "registration_email_taken",
    default=_email_is_free,
)


class RegistrationWorkflow:
    """LangGraph só orquestra. A transição mora no domínio.

    O construtor compila o grafo uma vez (`_compile`). O `AiRuntime` guarda a instância pelo
    processo inteiro, com o mesmo provedor de chat das perguntas e, portanto, o mesmo circuit
    breaker (seção 7.1). Os nós do grafo são os métodos `_extract`, `_decide` e `_phrase`. Sem
    `tracer`, o `NullTracer` descarta os rastros.
    """

    def __init__(self, chat: ChatProvider, tracer: TraceRecorder | None = None) -> None:
        self._chat = chat
        self._tracer = tracer or NullTracer()
        self.graph: Any = _compile(self)

    async def turn(
        self,
        machine: Machine,
        user_text: str,
        *,
        request_id: str,
        email_taken: EmailTaken | None = None,
    ) -> TurnResult:
        """Executa um turno do cadastro por chat e devolve a máquina nova e a frase.

        1. Cria o `run_id` do rastro e entrega `email_taken` aos nós pelo `ContextVar`.
        2. Roda o grafo: `extract`, `decide_next` e `phrase`.
        3. Confere a saída do grafo e escolhe a frase, com a pergunta modelo como reserva.
        4. Grava o rastro `metadata_only`: nomes dos campos aceitos, `next_step` e tokens,
           nunca os valores (seção 18.4).

        `email_taken` diz se um e-mail já tem conta; sem ela, nenhum conta como usado. Levanta
        `ProviderUnavailable` (ou `CircuitOpen`, que herda dela) quando a extração falha ou o
        grafo devolve algo inesperado; o serviço responde 503 e a tela oferece o formulário
        (seção 7.2). Nada é gravado no banco aqui: o serviço persiste a máquina.
        """
        # 1.
        run_id = uuid4()
        token = _email_taken.set(email_taken or _email_is_free)
        try:
            # 2. `ainvoke` roda os nós na ordem das arestas e devolve o estado final.
            raw = await self.graph.ainvoke(
                {
                    "machine": machine,
                    "user_text": user_text,
                    "request_id": request_id,
                    "prompt": "",
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "accepted_names": [],
                    "run_id": str(run_id),
                }
            )
        finally:
            # Volta o `ContextVar` ao valor anterior, também quando um nó levanta erro.
            _email_taken.reset(token)
        # 3. O grafo devolve `Any`. Estas conferências protegem o serviço de um estado inesperado.
        if not isinstance(raw, dict):
            raise ProviderUnavailable(REGISTRATION_UNAVAILABLE)
        updated = raw.get("machine")
        if not isinstance(updated, Machine):
            raise ProviderUnavailable(REGISTRATION_UNAVAILABLE)
        prompt = raw.get("prompt")
        text = (
            prompt
            if isinstance(prompt, str) and prompt
            else prompt_for(
                updated.next_step.value,
                correcting=updated.correcting,
            )
        )
        accepted = raw.get("accepted_names")
        if isinstance(accepted, list):
            names = tuple(item for item in accepted if isinstance(item, str))
        else:
            names = ()
        input_tokens = _count(raw.get("input_tokens"))
        output_tokens = _count(raw.get("output_tokens"))
        # 4. Só nomes de campos, passo e tokens. O domínio monta o evento com a política.
        self._tracer.record_many(
            [
                registration_event_from_record(
                    {
                        "field_names": list(names),
                        "next_step": updated.next_step.value,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                    },
                    run_id=run_id,
                )
            ]
        )
        return TurnResult(
            machine=updated,
            prompt=text,
            accepted_names=names,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    async def _extract(self, state: GraphState) -> dict[str, object]:
        """Nó `extract`: pede ao modelo os campos da mensagem pela ferramenta `set_fields`.

        1. Chama `complete_with_tools` com as regras, o passo atual e a mensagem do visitante.
        2. Lê a chamada pela lista de permissão do domínio: uma chave fora dela, como `role`,
           rejeita a saída inteira (seção 10.2). Sem chamada da ferramenta, nenhum campo muda.
        3. Troca um e-mail que já tem conta por um erro de campo, sem sobrescrever o e-mail
           guardado na máquina (seção 7.2).
        4. Aplica a leitura na máquina (`apply_collected`) e soma os tokens. Os erros de campo
           da máquina passam a ser só os deste turno.

        Não captura erro: uma falha do provedor sobe até `turn` e dali ao serviço.
        """
        machine = _machine(state)
        run = _run(
            state,
            prompt_version=EXTRACT_PROMPT_VERSION,
            temperature=EXTRACT_TEMPERATURE,
        )
        user_text = state.get("user_text", "")
        # 1.
        with traced_span(
            "registration.extract", run_id=run.run_id, model=self._chat.model_name
        ) as extract_span:
            result = await self._chat.complete_with_tools(
                [
                    # O passo atual diz ao modelo qual campo está sendo pedido, o que dá
                    # sentido a `skip_current`. Este trecho fica fora de `app/prompts` e do
                    # hash das versões, e o `DemoChatProvider` o lê pela expressão `_STEP`.
                    Message(
                        role="system",
                        content=f"{EXTRACT_INSTRUCTIONS}\nPasso atual: {machine.next_step.value}.",
                    ),
                    Message(role="user", content=user_text if isinstance(user_text, str) else ""),
                ],
                [_set_fields_tool()],
                run,
            )
        # 2. Uma resposta sem chamada, ou com outra ferramenta, vale como saída rejeitada.
        read = (
            read_tool_arguments(result.arguments)
            if result.name == SET_FIELDS_TOOL_NAME
            else rejected_tool()
        )
        # 3.
        read = await _drop_taken_email(read)
        accepted = () if read.rejected else tuple(read.values)
        # Esta linha roda depois de o `with` fechar o span, e o OpenTelemetry ignora atributo de
        # span encerrado: o `field_names` da seção 18.2 não chega ao `registration.extract`.
        extract_span.set(field_names=tuple(str(name) for name in accepted))
        # Evento `extracted` do funil da seção 18.3, só quando algum campo entrou. O evento
        # `optional_skipped`, da mesma lista, não é emitido por nenhum código.
        if accepted:
            REGISTRATION_EVENTS.labels(event="extracted", path="chat").inc()
        # 4.
        return {
            "machine": apply_collected(machine, read),
            "accepted_names": list(accepted),
            "input_tokens": _count(state.get("input_tokens")) + run.input_tokens,
            "output_tokens": _count(state.get("output_tokens")) + run.output_tokens,
        }

    def _decide(self, state: GraphState) -> dict[str, object]:
        """Nó `decide_next`: a função pura do domínio escolhe o próximo passo pelos campos.

        O modelo não participa. É aqui que a máquina de estados da seção 7.2 avança.
        """
        with traced_span("registration.decide") as decide_span:
            decided = decide_next(_machine(state))
            decide_span.set(next_step=decided.next_step.value)
        return {"machine": decided}

    async def _phrase(self, state: GraphState) -> dict[str, object]:
        """Nó `phrase`: a frase que o visitante lê neste turno.

        1. Com erro de campo, a resposta é fixa (`issue_reply`): explica o erro e pede o mesmo
           dado, sem o modelo, para ele não tratar o valor recusado como aceito.
        2. Na revisão, a resposta também é fixa (`review_prompt`): os campos entendidos, com
           os rótulos em português, e a pergunta final.
        3. Nos outros passos, o modelo reescreve a pergunta modelo do passo vendo a mensagem
           do visitante, para responder a uma dúvida antes de pedir o dado (seção 7.2).
        4. Se o modelo falha, ou devolve frase vazia ou longa demais, vale a pergunta modelo.
        """
        machine = _machine(state)
        # 1.
        if machine.field_errors:
            return {
                "prompt": issue_reply(
                    tuple((issue.field, issue.code) for issue in machine.field_errors),
                    machine.next_step.value,
                    correcting=machine.correcting,
                )
            }
        # 2.
        if machine.next_step == Step.REVIEW and not machine.correcting:
            return {"prompt": review_prompt(asdict(public_fields(machine.fields)))}
        # 3.
        fallback = prompt_for(machine.next_step.value, correcting=machine.correcting)
        run = _run(state, prompt_version=PHRASE_PROMPT_VERSION, temperature=PHRASE_TEMPERATURE)
        user_text = state.get("user_text", "")
        message = user_text.strip() if isinstance(user_text, str) else ""
        try:
            phrase = await self._chat.complete_structured(
                [
                    Message(role="system", content=PHRASE_INSTRUCTIONS),
                    Message(
                        role="user",
                        content=(
                            f"passo: {machine.next_step.value}\n"
                            f"pergunta modelo: {fallback}\n"
                            f"mensagem: {message}"
                        ),
                    ),
                ],
                PhraseText,
                run,
            )
        # 4. Inclui o `CircuitOpen`. A falha da frase não derruba o turno: a extração já valeu.
        except ProviderUnavailable:
            text = fallback
        else:
            candidate = phrase.text.strip()
            text = candidate if candidate and len(candidate) <= MAX_PHRASE_CHARS else fallback
        return {
            "prompt": text,
            "input_tokens": _count(state.get("input_tokens")) + run.input_tokens,
            "output_tokens": _count(state.get("output_tokens")) + run.output_tokens,
        }


def _compile(workflow: RegistrationWorkflow) -> Any:
    """Monta e compila o grafo, em linha: START, `extract`, `decide_next`, `phrase` e END.

    Um `StateGraph` do LangGraph liga nós, que são funções que recebem o estado e devolvem as
    chaves que mudaram, por arestas. `compile()` sem checkpointer gera um grafo sem memória
    entre execuções: cada `ainvoke` começa do estado que `turn` passa (seção 7.2). O import
    fica aqui dentro para o LangGraph carregar só quando o workflow nasce.
    """
    from langgraph.graph import END, START, StateGraph

    builder: StateGraph[GraphState] = StateGraph(GraphState)
    builder.add_node("extract", workflow._extract)
    builder.add_node("decide_next", workflow._decide)
    builder.add_node("phrase", workflow._phrase)
    builder.add_edge(START, "extract")
    builder.add_edge("extract", "decide_next")
    builder.add_edge("decide_next", "phrase")
    builder.add_edge("phrase", END)
    return builder.compile()


def _set_fields_tool() -> Tool:
    """A ferramenta `set_fields`: o schema do domínio com as descrições em português.

    As chaves, os enums e `additionalProperties: false` vêm de `set_fields_parameters`, a lista
    de permissão da seção 10.2. As descrições de `app.prompts.registration` só entram nas
    propriedades que já existem no schema, então não acrescentam campo.
    """
    parameters = set_fields_parameters()
    properties = parameters.get("properties")
    if isinstance(properties, dict):
        for name, description in TOOL_PROPERTY_DESCRIPTIONS.items():
            field = properties.get(name)
            if isinstance(field, dict):
                properties[name] = {**field, "description": description}
    return Tool(
        name=SET_FIELDS_TOOL_NAME,
        description=SET_FIELDS_DESCRIPTION,
        parameters=parameters,
    )


async def _drop_taken_email(read: ToolRead) -> ToolRead:
    """Tira da leitura um e-mail que já tem conta e registra o erro `email/taken`.

    Usa a consulta do pedido, guardada no `ContextVar`. O e-mail da máquina não muda.
    """
    if read.rejected or "email" not in read.values:
        return read
    if await _email_taken.get()(read.values["email"]):
        return read.without_email()
    return read


def _machine(state: GraphState) -> Machine:
    """A `Machine` do estado. Sem ela, o turno falha como cadastro indisponível."""
    machine = state.get("machine")
    if not isinstance(machine, Machine):
        raise ProviderUnavailable(REGISTRATION_UNAVAILABLE)
    return machine


def _run(state: GraphState, *, prompt_version: str, temperature: float) -> RunContext:
    """O `RunContext` de um nó, com o `run_id` do turno e a tag `registration`.

    A política é `metadata_only` em todos os nós (seção 18.4). Um `run_id` ilegível ganha um
    novo.
    """
    raw = state.get("run_id", "")
    try:
        run_id = UUID(raw)
    except ValueError:
        run_id = uuid4()
    return RunContext(
        run_id=run_id,
        request_id=state.get("request_id", ""),
        prompt_version=prompt_version,
        trace_policy="metadata_only",
        tags=("registration",),
        temperature=temperature,
    )


def _count(value: object) -> int:
    """Uma contagem de tokens lida do estado. `bool` é subclasse de `int`, então é recusado."""
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value
