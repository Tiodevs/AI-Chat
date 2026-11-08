"""O adaptador de chat: tempo limite, nova tentativa, circuit breaker e leitura do LangChain.

Seções 5.3, 7.1 e 17 do SDD. O `GeminiChatProvider` roda sobre o falso `_Backend`, com o
relógio `_Clock` e uma espera falsa, então 429 e 503 repetem depois de 20 s sem esperar de
verdade e cinco falhas abrem o circuito por 60 s. Os falsos `_StructuredModel`, `_ToolModel`
e `_TalkModel` fazem o papel do `ChatGoogleGenerativeAI` dentro do `LangChainChatBackend`.
`build_langchain_model` monta o modelo de verdade, com uma chave de teste, sem chamá-lo. Não
usa banco nem rede.
"""

import asyncio
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import BaseModel

from app.adapters.gemini_chat import GeminiChatProvider
from app.adapters.langchain_chat import (
    CHAT_TIMEOUT_SECONDS,
    LangChainChatBackend,
    build_langchain_model,
    message_text,
    message_usage,
)
from app.adapters.provider_status import retryable_status
from app.domain.errors import CircuitOpen, ProviderUnavailable
from app.ports.chat import Message, RunContext, TokenUsage, Tool, ToolResult


class _Note(BaseModel):
    """Schema de saída estruturada mínimo; o padrão `ok` dispensa dados do falso."""

    text: str = "ok"


def test_langchain_model_uses_a_one_hundred_twenty_second_timeout_and_no_sdk_retries() -> None:
    model = build_langchain_model(
        model="gemini-2.5-flash",
        api_key="test-key",
        timeout_seconds=CHAT_TIMEOUT_SECONDS,
        temperature=0,
    )
    assert model.timeout == 120
    assert model.max_retries == 0
    assert model.temperature == 0
    assert model.thinking_budget == 0
    assert model.vertexai is False
    copied = model.model_copy(update={"temperature": 0.2})
    assert copied.temperature == 0.2
    assert copied.thinking_budget == 0
    assert model.temperature == 0
    assert CHAT_TIMEOUT_SECONDS == 120


def test_message_text_reads_gemini_content_blocks() -> None:
    message = SimpleNamespace(
        content=[{"type": "text", "text": "Horário "}, {"type": "text", "text": "11:00"}],
        usage_metadata={"input_tokens": 4, "output_tokens": 2},
    )
    assert message_text(message) == "Horário 11:00"
    assert message_usage(message) == TokenUsage(4, 2)
    assert message_text(SimpleNamespace(content="direto")) == "direto"


def test_genai_error_code_is_retryable() -> None:
    assert retryable_status(_StatusError(429))
    assert retryable_status(_CodeError(503))
    assert not retryable_status(_StatusError(500))
    assert not retryable_status(RuntimeError("down"))


def test_a_429_is_retried_and_a_500_is_not() -> None:
    backend = _Backend(failures=1, status=429)
    slept: list[float] = []
    provider = _provider(backend, sleep=_record(slept))
    result = asyncio.run(provider.complete_structured([], _Note, _context()))
    assert result.text == "ok"
    assert backend.calls == 2
    assert slept == [20.0]
    assert backend.temperatures == [0.0, 0.0]

    plain = _Backend(failures=1, status=500)
    with pytest.raises(ProviderUnavailable) as caught:
        asyncio.run(_provider(plain, sleep=_record([])).complete_structured([], _Note, _context()))
    assert type(caught.value) is ProviderUnavailable
    assert plain.calls == 1


def test_a_503_is_retried() -> None:
    backend = _Backend(failures=1, status=503)
    slept: list[float] = []
    asyncio.run(
        _provider(backend, sleep=_record(slept)).complete_structured([], _Note, _context())
    )
    assert backend.calls == 2
    assert slept == [20.0]


def test_exhausted_retries_count_as_one_failure() -> None:
    # Cada pedido faz 3 tentativas e conta uma falha no circuito: 5 pedidos, 15 chamadas, e o
    # sexto pedido para no circuito aberto sem chegar ao backend.
    backend = _Backend(failures=100, status=429)
    provider = _provider(backend)
    for _ in range(5):
        with pytest.raises(ProviderUnavailable) as caught:
            asyncio.run(provider.complete_structured([], _Note, _context()))
        assert type(caught.value) is ProviderUnavailable
    assert backend.calls == 15
    with pytest.raises(CircuitOpen):
        asyncio.run(provider.complete_structured([], _Note, _context()))
    assert backend.calls == 15


def test_five_failures_open_the_circuit_for_sixty_seconds() -> None:
    clock = _Clock()
    backend = _Backend(failures=100, status=500)
    provider = _provider(backend, clock=clock)
    for _ in range(5):
        with pytest.raises(ProviderUnavailable):
            asyncio.run(provider.complete_structured([], _Note, _context()))
    with pytest.raises(CircuitOpen):
        asyncio.run(provider.complete_structured([], _Note, _context()))
    assert backend.calls == 5
    clock.advance(59)
    with pytest.raises(CircuitOpen):
        asyncio.run(provider.complete_structured([], _Note, _context()))
    assert backend.calls == 5
    clock.advance(1)
    backend.failures = 0
    asyncio.run(provider.complete_structured([], _Note, _context(temperature=0.2)))
    assert backend.calls == 6
    assert backend.temperatures[-1] == 0.2


def test_timeout_fails_the_attempt_without_a_retry() -> None:
    backend = _Backend(sleep_seconds=1)
    started = time.monotonic()
    with pytest.raises(ProviderUnavailable) as caught:
        asyncio.run(
            _provider(backend, timeout_seconds=0.05).complete_structured([], _Note, _context())
        )
    assert type(caught.value) is ProviderUnavailable
    assert backend.calls == 1
    assert time.monotonic() - started < 0.5


def test_stream_sums_usage_and_passes_the_answer_temperature() -> None:
    backend = _Backend()
    provider = _provider(backend)
    run = _context(temperature=0.2)

    async def collect() -> str:
        return "".join([token async for token in provider.stream([], run)])

    assert asyncio.run(collect()) == "Olá [1]"
    assert run.input_tokens == 1
    assert run.output_tokens == 3
    assert backend.temperatures == [0.2]


def test_structured_output_reads_the_raw_message_usage() -> None:
    model = _StructuredModel()
    backend = LangChainChatBackend(model)

    async def run() -> tuple[object, TokenUsage]:
        return await backend.complete_structured(
            [Message(role="user", content="oi")],
            _Note,
            0.2,
        )

    parsed, usage = asyncio.run(run())
    assert isinstance(parsed, _Note)
    assert parsed.text == "pronto"
    assert usage == TokenUsage(8, 2)
    assert model.temperatures == [0.2]


def test_tool_call_is_read_from_the_model_message() -> None:
    model = _ToolModel()
    backend = LangChainChatBackend(model)
    tool = Tool(name="set_fields", description="Grava campos.", parameters={"type": "object"})

    async def run() -> ToolResult:
        result, _usage = await backend.complete_with_tools(
            [Message(role="user", content="Ana")],
            [tool],
            0,
        )
        return result

    result = asyncio.run(run())
    assert result.name == "set_fields"
    assert result.arguments == {"full_name": "Ana"}


def test_a_reply_without_a_tool_call_keeps_the_text() -> None:
    model = _TalkModel()
    backend = LangChainChatBackend(model)
    tool = Tool(name="set_fields", description="Grava campos.", parameters={"type": "object"})

    async def run() -> ToolResult:
        result, _usage = await backend.complete_with_tools(
            [Message(role="user", content="O que seria o melhor email?")],
            [tool],
            0,
        )
        return result

    result = asyncio.run(run())
    assert result.name == ""
    assert result.arguments == {}
    assert result.text == "Use um e-mail que você abre com frequência."


class _TalkModel:
    """Falso do modelo LangChain que responde com texto, sem chamar a ferramenta."""

    temperature = 0.0

    def model_copy(self, *, update: dict[str, float]) -> "_TalkModel":
        copied = _TalkModel()
        copied.temperature = update["temperature"]
        return copied

    def bind_tools(self, tools: list[dict[str, object]], **kwargs: object) -> "_TalkModel":
        del tools, kwargs
        return self

    async def ainvoke(
        self,
        messages: list[tuple[str, str]],
        **kwargs: object,
    ) -> SimpleNamespace:
        del messages, kwargs
        return SimpleNamespace(
            content="Use um e-mail que você abre com frequência.",
            tool_calls=[],
            usage_metadata={"input_tokens": 4, "output_tokens": 2},
        )


class _StatusError(Exception):
    """Erro de provedor com o status HTTP em `status_code`."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"status {status_code}")
        self.status_code = status_code


class _CodeError(Exception):
    """Erro de provedor com o status em `code`, como os erros do SDK `google-genai`."""

    def __init__(self, code: int) -> None:
        super().__init__(str(code))
        self.code = code


class _Clock:
    """Relógio que só anda com `advance`, para abrir e fechar o circuito sem esperar."""

    def __init__(self) -> None:
        self.moment = datetime(2026, 10, 27, tzinfo=UTC)

    def now(self) -> datetime:
        return self.moment

    def advance(self, seconds: float) -> None:
        self.moment += timedelta(seconds=seconds)


class _Backend:
    """Falso do `ChatBackend`: falha `failures` vezes com `status`, conta chamadas e temperaturas.

    `sleep_seconds` atrasa a saída estruturada para o tempo limite vencer. O fluxo devolve
    `Olá [1]` em dois pedaços, com o uso de cada um.
    """

    def __init__(
        self,
        *,
        failures: int = 0,
        status: int = 500,
        sleep_seconds: float = 0,
    ) -> None:
        self.failures = failures
        self.status = status
        self.sleep_seconds = sleep_seconds
        self.calls = 0
        self.temperatures: list[float] = []

    async def complete_structured(
        self,
        messages: list[Message],
        schema: type[BaseModel],
        temperature: float,
    ) -> tuple[BaseModel, TokenUsage]:
        del messages
        self.calls += 1
        self.temperatures.append(temperature)
        if self.sleep_seconds:
            await asyncio.sleep(self.sleep_seconds)
        if self.failures:
            self.failures -= 1
            raise _StatusError(self.status)
        return schema.model_validate({}), TokenUsage(1, 1)

    async def complete_with_tools(
        self,
        messages: list[Message],
        tools: list[Tool],
        temperature: float,
    ) -> tuple[ToolResult, TokenUsage]:
        raise AssertionError((messages, tools, temperature))

    def stream(
        self,
        messages: list[Message],
        temperature: float,
    ) -> AsyncIterator[tuple[str, TokenUsage]]:
        del messages

        async def iterate() -> AsyncIterator[tuple[str, TokenUsage]]:
            self.calls += 1
            self.temperatures.append(temperature)
            yield "Olá", TokenUsage(1, 1)
            yield " [1]", TokenUsage(0, 2)

        return iterate()


class _StructuredModel:
    """Falso do modelo LangChain para `with_structured_output(include_raw=True)`.

    Devolve o objeto validado e a mensagem crua com `usage_metadata`, e guarda a temperatura
    de cada chamada.
    """

    def __init__(self) -> None:
        self.temperature = 0.0
        self.temperatures: list[float] = []

    def model_copy(self, *, update: dict[str, float]) -> "_StructuredModel":
        copied = _StructuredModel()
        copied.temperature = update["temperature"]
        copied.temperatures = self.temperatures
        return copied

    def with_structured_output(self, schema: type[BaseModel], *, include_raw: bool) -> object:
        assert include_raw is True
        model = self

        class _Runnable:
            async def ainvoke(
                self,
                messages: list[tuple[str, str]],
                **kwargs: object,
            ) -> dict[str, object]:
                del messages
                model.temperatures.append(float(kwargs["temperature"]))  # type: ignore[arg-type]
                return {
                    "parsed": schema.model_validate({"text": "pronto"}),
                    "parsing_error": None,
                    "raw": SimpleNamespace(
                        usage_metadata={"input_tokens": 8, "output_tokens": 2}
                    ),
                }

        return _Runnable()


class _ToolModel:
    """Falso do modelo LangChain que chama `set_fields` com o nome `Ana`."""

    temperature = 0.0

    def model_copy(self, *, update: dict[str, float]) -> "_ToolModel":
        copied = _ToolModel()
        copied.temperature = update["temperature"]
        return copied

    def bind_tools(self, tools: list[dict[str, object]], **kwargs: object) -> "_ToolModel":
        assert tools[0]["type"] == "function"
        assert kwargs == {}
        return self

    async def ainvoke(
        self,
        messages: list[tuple[str, str]],
        **kwargs: object,
    ) -> SimpleNamespace:
        del messages, kwargs
        return SimpleNamespace(
            tool_calls=[{"name": "set_fields", "args": {"full_name": "Ana"}}],
            usage_metadata={"input_tokens": 3, "output_tokens": 1},
        )


def _provider(
    backend: _Backend,
    *,
    clock: _Clock | None = None,
    sleep: object | None = None,
    timeout_seconds: float = 20,
) -> GeminiChatProvider:
    """`GeminiChatProvider` sobre o `_Backend`, com relógio falso e espera que volta na hora."""

    async def immediate(_delay: float) -> None:
        return None

    if sleep is None:
        sleep = immediate
    return GeminiChatProvider(
        api_key="test-key",
        model="gemini-2.5-flash",
        clock=clock or _Clock(),
        sleep=sleep,  # type: ignore[arg-type]
        backend=backend,
        timeout_seconds=timeout_seconds,
    )


def _record(slept: list[float]) -> object:
    """Espera falsa que anota em `slept` cada atraso pedido, sem esperar."""

    async def sleep(delay: float) -> None:
        slept.append(delay)

    return sleep


def _context(*, temperature: float = 0) -> RunContext:
    """`RunContext` de uma chamada de reescrita, com a temperatura pedida."""
    return RunContext(
        run_id=uuid4(),
        request_id="req-1",
        prompt_version="qa-rewrite@2026-10-27.1",
        trace_policy="metadata_only",
        temperature=temperature,
    )
