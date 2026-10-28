"""Grafo do cadastro: extract, decide_next e phrase. Sem checkpointer. Seção 7.2."""

from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, TypedDict
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.domain.errors import ProviderUnavailable
from app.domain.fields import (
    SET_FIELDS_TOOL_NAME,
    ToolRead,
    read_tool_arguments,
    rejected_tool,
    set_fields_parameters,
)
from app.domain.registration import Machine, apply_collected, decide_next
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
    prompt_for,
)

EXTRACT_TEMPERATURE = 0.0
PHRASE_TEMPERATURE = 0.2
MAX_PHRASE_CHARS = 500

EmailTaken = Callable[[str], Awaitable[bool]]


class PhraseText(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str = Field(description=PHRASE_TEXT_DESCRIPTION)


class GraphState(TypedDict, total=False):
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
    machine: Machine
    prompt: str
    accepted_names: tuple[str, ...]
    input_tokens: int
    output_tokens: int


async def _email_is_free(_email: str) -> bool:
    return False


_email_taken: ContextVar[EmailTaken] = ContextVar(
    "registration_email_taken",
    default=_email_is_free,
)


class RegistrationWorkflow:
    """LangGraph só orquestra. A transição mora no domínio."""

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
        run_id = uuid4()
        token = _email_taken.set(email_taken or _email_is_free)
        try:
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
            _email_taken.reset(token)
        if not isinstance(raw, dict):
            raise ProviderUnavailable(REGISTRATION_UNAVAILABLE)
        updated = raw.get("machine")
        if not isinstance(updated, Machine):
            raise ProviderUnavailable(REGISTRATION_UNAVAILABLE)
        prompt = raw.get("prompt")
        text = prompt if isinstance(prompt, str) and prompt else prompt_for(
            updated.next_step.value,
            correcting=updated.correcting,
        )
        accepted = raw.get("accepted_names")
        if isinstance(accepted, list):
            names = tuple(item for item in accepted if isinstance(item, str))
        else:
            names = ()
        input_tokens = _count(raw.get("input_tokens"))
        output_tokens = _count(raw.get("output_tokens"))
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
        machine = _machine(state)
        run = _run(
            state,
            prompt_version=EXTRACT_PROMPT_VERSION,
            temperature=EXTRACT_TEMPERATURE,
        )
        user_text = state.get("user_text", "")
        result = await self._chat.complete_with_tools(
            [
                Message(
                    role="system",
                    content=f"{EXTRACT_INSTRUCTIONS}\nPasso atual: {machine.next_step.value}.",
                ),
                Message(role="user", content=user_text if isinstance(user_text, str) else ""),
            ],
            [_set_fields_tool()],
            run,
        )
        read = (
            read_tool_arguments(result.arguments)
            if result.name == SET_FIELDS_TOOL_NAME
            else rejected_tool()
        )
        read = await _drop_taken_email(read)
        accepted = () if read.rejected else tuple(read.values)
        return {
            "machine": apply_collected(machine, read),
            "accepted_names": list(accepted),
            "input_tokens": _count(state.get("input_tokens")) + run.input_tokens,
            "output_tokens": _count(state.get("output_tokens")) + run.output_tokens,
        }

    def _decide(self, state: GraphState) -> dict[str, object]:
        return {"machine": decide_next(_machine(state))}

    async def _phrase(self, state: GraphState) -> dict[str, object]:
        machine = _machine(state)
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
                        content=f"passo: {machine.next_step.value}\nmensagem: {message}",
                    ),
                ],
                PhraseText,
                run,
            )
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
    if read.rejected or "email" not in read.values:
        return read
    if await _email_taken.get()(read.values["email"]):
        return read.without_email()
    return read


def _machine(state: GraphState) -> Machine:
    machine = state.get("machine")
    if not isinstance(machine, Machine):
        raise ProviderUnavailable(REGISTRATION_UNAVAILABLE)
    return machine


def _run(state: GraphState, *, prompt_version: str, temperature: float) -> RunContext:
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
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value
