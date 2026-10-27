"""ChatGoogleGenerativeAI atrás da porta de chat. Seção 17 do SDD."""

from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel

from app.ports.chat import Message, TokenUsage, Tool, ToolResult

CHAT_TIMEOUT_SECONDS = 120.0
SDK_MAX_RETRIES = 0
THINKING_BUDGET = 0


class ChatResponseError(Exception):
    """A resposta do modelo não pôde ser lida. Sem texto de prompt."""


class LangChainChatBackend:
    def __init__(self, model: Any) -> None:
        self._model = model

    async def complete_structured(
        self,
        messages: list[Message],
        schema: type[BaseModel],
        temperature: float,
    ) -> tuple[BaseModel, TokenUsage]:
        model = self._at(temperature)
        structured = model.with_structured_output(schema, include_raw=True)
        payload = await structured.ainvoke(_to_langchain(messages), temperature=temperature)
        parsed = _parse_structured(payload, schema)
        raw = payload.get("raw") if isinstance(payload, dict) else None
        return parsed, _usage(raw)

    async def complete_with_tools(
        self,
        messages: list[Message],
        tools: list[Tool],
        temperature: float,
    ) -> tuple[ToolResult, TokenUsage]:
        model = self._at(temperature)
        bound = model.bind_tools([_tool_spec(tool) for tool in tools])
        message = await bound.ainvoke(_to_langchain(messages), temperature=temperature)
        return _tool_result(message), message_usage(message)

    def stream(
        self,
        messages: list[Message],
        temperature: float,
    ) -> AsyncIterator[tuple[str, TokenUsage]]:
        return self._stream(messages, temperature)

    async def _stream(
        self,
        messages: list[Message],
        temperature: float,
    ) -> AsyncIterator[tuple[str, TokenUsage]]:
        model = self._at(temperature)
        async for chunk in model.astream(_to_langchain(messages), temperature=temperature):
            yield message_text(chunk), message_usage(chunk)

    def _at(self, temperature: float) -> Any:
        if getattr(self._model, "temperature", None) == temperature:
            return self._model
        return self._model.model_copy(update={"temperature": temperature})


def build_langchain_model(
    *,
    model: str,
    api_key: str,
    timeout_seconds: float,
    temperature: float,
) -> Any:
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=model,
        api_key=api_key,
        timeout=timeout_seconds,
        temperature=temperature,
        max_retries=SDK_MAX_RETRIES,
        vertexai=False,
        thinking_budget=THINKING_BUDGET,
    )


def message_text(message: object) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


def message_usage(message: object) -> TokenUsage:
    raw = getattr(message, "usage_metadata", None)
    if not isinstance(raw, dict):
        return TokenUsage()
    return TokenUsage(
        input_tokens=_count(raw.get("input_tokens")),
        output_tokens=_count(raw.get("output_tokens")),
    )


def _parse_structured(payload: object, schema: type[BaseModel]) -> BaseModel:
    if not isinstance(payload, dict):
        raise ChatResponseError("structured")
    parsing_error = payload.get("parsing_error")
    if isinstance(parsing_error, Exception):
        raise ChatResponseError("structured") from parsing_error
    if parsing_error is not None:
        raise ChatResponseError("structured")
    parsed = payload.get("parsed")
    if isinstance(parsed, schema):
        return parsed
    if isinstance(parsed, dict):
        return schema.model_validate(parsed)
    raise ChatResponseError("structured")


def _usage(message: object) -> TokenUsage:
    if message is None:
        return TokenUsage()
    return message_usage(message)


def _tool_result(message: object) -> ToolResult:
    calls = getattr(message, "tool_calls", None)
    if not isinstance(calls, list) or not calls:
        raise ChatResponseError("tool")
    call = calls[0]
    if isinstance(call, dict):
        name = call.get("name")
        arguments = call.get("args", {})
    else:
        name = getattr(call, "name", None)
        arguments = getattr(call, "args", {})
    if not isinstance(name, str) or not isinstance(arguments, dict):
        raise ChatResponseError("tool")
    return ToolResult(
        name=name,
        arguments={str(key): value for key, value in arguments.items()},
    )


def _tool_spec(tool: Tool) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def _to_langchain(messages: list[Message]) -> list[tuple[str, str]]:
    roles = {"system": "system", "user": "human", "assistant": "ai"}
    return [(roles[message.role], message.content) for message in messages]


def _count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(value, 0)
