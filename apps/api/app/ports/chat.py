"""Porta de chat. Seção 17 do SDD."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal, Protocol, TypeVar
from uuid import UUID

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)
TracePolicy = Literal["full", "masked", "metadata_only"]
MessageRole = Literal["system", "user", "assistant"]


@dataclass(frozen=True, slots=True)
class Message:
    role: MessageRole
    content: str


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, object]


@dataclass(frozen=True, slots=True)
class ToolResult:
    name: str
    arguments: dict[str, object]
    text: str = ""


@dataclass(frozen=True, slots=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(slots=True)
class RunContext:
    """Temperatura da chamada e tokens preenchidos pelo adaptador. Seção 17 do SDD."""

    run_id: UUID
    request_id: str
    prompt_version: str
    trace_policy: TracePolicy
    tags: tuple[str, ...] = ()
    temperature: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(slots=True)
class UsageTally:
    """Os `RunContext` de um pedido. Seções 6.4 e 7.1 do SDD.

    O adaptador soma os tokens no `RunContext` a cada pedaço do fluxo, então a soma vale também
    no meio de uma resposta cancelada.
    """

    runs: list[RunContext] = field(default_factory=list)

    def track(self, run: RunContext) -> RunContext:
        self.runs.append(run)
        return run

    @property
    def input_tokens(self) -> int:
        return sum(run.input_tokens for run in self.runs)

    @property
    def output_tokens(self) -> int:
        return sum(run.output_tokens for run in self.runs)


class ChatProvider(Protocol):
    model_name: str

    async def complete_structured(
        self,
        messages: list[Message],
        schema: type[ModelT],
        run: RunContext,
    ) -> ModelT: ...

    async def complete_with_tools(
        self,
        messages: list[Message],
        tools: list[Tool],
        run: RunContext,
    ) -> ToolResult: ...

    def stream(self, messages: list[Message], run: RunContext) -> AsyncIterator[str]: ...
