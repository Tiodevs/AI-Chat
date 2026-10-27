"""GeminiChatProvider: 120 s, nova tentativa em 429 e 503, circuito 5/60 s. Seção 17."""

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Protocol, TypeVar

import structlog
from pydantic import BaseModel

from app.adapters.circuit_breaker import CircuitBreaker
from app.adapters.clock import SystemClock
from app.adapters.langchain_chat import CHAT_TIMEOUT_SECONDS
from app.adapters.provider_status import http_status, retryable_status
from app.domain.errors import CircuitOpen, ProviderUnavailable
from app.ports.chat import Message, ModelT, RunContext, TokenUsage, Tool, ToolResult
from app.ports.clock import Clock
from app.prompts.qa import CHAT_UNAVAILABLE, CIRCUIT_OPEN_MESSAGE

CHAT_ATTEMPTS = 3
CHAT_RETRY_DELAY_SECONDS = 20.0
T = TypeVar("T")


class ChatBackend(Protocol):
    async def complete_structured(
        self,
        messages: list[Message],
        schema: type[BaseModel],
        temperature: float,
    ) -> tuple[BaseModel, TokenUsage]: ...

    async def complete_with_tools(
        self,
        messages: list[Message],
        tools: list[Tool],
        temperature: float,
    ) -> tuple[ToolResult, TokenUsage]: ...

    def stream(
        self,
        messages: list[Message],
        temperature: float,
    ) -> AsyncIterator[tuple[str, TokenUsage]]: ...


class GeminiChatProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        clock: Clock | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        backend: ChatBackend | None = None,
        timeout_seconds: float = CHAT_TIMEOUT_SECONDS,
    ) -> None:
        self.model_name = model
        self._timeout = timeout_seconds
        self._sleep = sleep or asyncio.sleep
        self._breaker = CircuitBreaker(clock or SystemClock())
        self._backend = backend or _default_backend(
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
        )

    async def complete_structured(
        self,
        messages: list[Message],
        schema: type[ModelT],
        run: RunContext,
    ) -> ModelT:
        value, usage = await self._attempt(
            lambda: self._backend.complete_structured(messages, schema, run.temperature)
        )
        _add_usage(run, usage)
        if isinstance(value, schema):
            return value
        raise ProviderUnavailable(CHAT_UNAVAILABLE)

    async def complete_with_tools(
        self,
        messages: list[Message],
        tools: list[Tool],
        run: RunContext,
    ) -> ToolResult:
        value, usage = await self._attempt(
            lambda: self._backend.complete_with_tools(messages, tools, run.temperature)
        )
        _add_usage(run, usage)
        return value

    def stream(self, messages: list[Message], run: RunContext) -> AsyncIterator[str]:
        return self._stream(messages, run)

    async def _stream(self, messages: list[Message], run: RunContext) -> AsyncIterator[str]:
        self._refuse_if_open()
        delay = CHAT_RETRY_DELAY_SECONDS
        for attempt in range(1, CHAT_ATTEMPTS + 1):
            yielded = False
            try:
                async for text in self._read_attempt(messages, run):
                    yielded = True
                    if text:
                        yield text
            except TimeoutError as exc:
                self._record_provider_failure(exc)
                raise ProviderUnavailable(CHAT_UNAVAILABLE) from exc
            except CircuitOpen:
                raise
            except Exception as exc:
                if not yielded and retryable_status(exc) and attempt < CHAT_ATTEMPTS:
                    await self._sleep(delay)
                    delay *= 2
                    continue
                self._record_provider_failure(exc)
                raise ProviderUnavailable(CHAT_UNAVAILABLE) from exc
            else:
                self._breaker.record_success()
                return
        self._breaker.record_failure()
        raise ProviderUnavailable(CHAT_UNAVAILABLE)

    async def _read_attempt(
        self,
        messages: list[Message],
        run: RunContext,
    ) -> AsyncIterator[str]:
        iterator = self._backend.stream(messages, run.temperature).__aiter__()
        deadline = time.monotonic() + self._timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            item = await asyncio.wait_for(_next_chunk(iterator), remaining)
            if item is None:
                return
            text, usage = item
            _add_usage(run, usage)
            yield text

    async def _attempt(self, operation: Callable[[], Awaitable[T]]) -> T:
        self._refuse_if_open()
        delay = CHAT_RETRY_DELAY_SECONDS
        last: BaseException | None = None
        for attempt in range(1, CHAT_ATTEMPTS + 1):
            try:
                async with asyncio.timeout(self._timeout):
                    result = await operation()
            except TimeoutError as exc:
                self._record_provider_failure(exc)
                raise ProviderUnavailable(CHAT_UNAVAILABLE) from exc
            except CircuitOpen:
                raise
            except Exception as exc:
                last = exc
                if retryable_status(exc) and attempt < CHAT_ATTEMPTS:
                    await self._sleep(delay)
                    delay *= 2
                    continue
                self._record_provider_failure(exc)
                raise ProviderUnavailable(CHAT_UNAVAILABLE) from exc
            else:
                self._breaker.record_success()
                return result
        self._breaker.record_failure()
        raise ProviderUnavailable(CHAT_UNAVAILABLE) from last

    def _refuse_if_open(self) -> None:
        if not self._breaker.allow():
            raise CircuitOpen(CIRCUIT_OPEN_MESSAGE)

    def _record_provider_failure(self, exc: BaseException) -> None:
        self._breaker.record_failure()
        structlog.get_logger("atrium").warning(
            "chat.provider_failed",
            error_type=type(exc).__name__,
            status_code=http_status(exc),
        )


def _default_backend(*, api_key: str, model: str, timeout_seconds: float) -> ChatBackend:
    from app.adapters.langchain_chat import LangChainChatBackend, build_langchain_model

    built = build_langchain_model(
        model=model,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        temperature=0,
    )
    return LangChainChatBackend(built)


def _add_usage(run: RunContext, usage: TokenUsage) -> None:
    run.input_tokens += usage.input_tokens
    run.output_tokens += usage.output_tokens


async def _next_chunk(
    iterator: AsyncIterator[tuple[str, TokenUsage]],
) -> tuple[str, TokenUsage] | None:
    try:
        return await anext(iterator)
    except StopAsyncIteration:
        return None
