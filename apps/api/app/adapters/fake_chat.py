"""Chat falso para testes. Seção 17 do SDD."""

from collections.abc import AsyncIterator, Sequence

from pydantic import BaseModel

from app.domain.errors import ProviderUnavailable
from app.ports.chat import Message, ModelT, RunContext, Tool, ToolResult
from app.prompts.qa import CHAT_UNAVAILABLE


class FakeChatProvider:
    def __init__(
        self,
        *,
        structured: BaseModel | Exception | None = None,
        tokens: Sequence[str] | Exception | None = None,
        tool_result: ToolResult | Exception | None = None,
        structured_usage: tuple[int, int] = (0, 0),
        stream_usage: tuple[int, int] = (0, 0),
        tool_usage: tuple[int, int] = (0, 0),
        model_name: str = "fake-chat",
    ) -> None:
        self.model_name = model_name
        self.structured_calls: list[tuple[tuple[Message, ...], RunContext]] = []
        self.stream_calls: list[tuple[tuple[Message, ...], RunContext]] = []
        self.tool_calls: list[tuple[tuple[Message, ...], tuple[Tool, ...], RunContext]] = []
        self._structured = structured
        self._tokens = tokens
        self._tool_result = tool_result
        self._structured_usage = structured_usage
        self._stream_usage = stream_usage
        self._tool_usage = tool_usage

    async def complete_structured(
        self,
        messages: list[Message],
        schema: type[ModelT],
        run: RunContext,
    ) -> ModelT:
        self.structured_calls.append((tuple(messages), run))
        if isinstance(self._structured, Exception):
            raise self._structured
        run.input_tokens += self._structured_usage[0]
        run.output_tokens += self._structured_usage[1]
        if isinstance(self._structured, schema):
            return self._structured
        raise ProviderUnavailable(CHAT_UNAVAILABLE)

    async def complete_with_tools(
        self,
        messages: list[Message],
        tools: list[Tool],
        run: RunContext,
    ) -> ToolResult:
        self.tool_calls.append((tuple(messages), tuple(tools), run))
        if isinstance(self._tool_result, Exception):
            raise self._tool_result
        run.input_tokens += self._tool_usage[0]
        run.output_tokens += self._tool_usage[1]
        if isinstance(self._tool_result, ToolResult):
            return self._tool_result
        raise ProviderUnavailable(CHAT_UNAVAILABLE)

    def stream(self, messages: list[Message], run: RunContext) -> AsyncIterator[str]:
        async def iterate() -> AsyncIterator[str]:
            self.stream_calls.append((tuple(messages), run))
            if isinstance(self._tokens, Exception):
                raise self._tokens
            for token in self._tokens or ():
                yield token
            run.input_tokens += self._stream_usage[0]
            run.output_tokens += self._stream_usage[1]

        return iterate()
