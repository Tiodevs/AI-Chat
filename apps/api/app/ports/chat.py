"""Porta de chat. Seção 17 do SDD."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
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
