"""GeminiChatProvider: 120 s, nova tentativa em 429 e 503, circuito 5/60 s. Seção 17.

Adaptador da porta de chat (`app.ports.chat`, seção 6.2). Este arquivo guarda a resiliência:
tempo limite, novas tentativas, circuit breaker e a contagem de tokens no `RunContext`. A
chamada ao modelo em si fica atrás do protocolo `ChatBackend`, que `langchain_chat` implementa
com o `ChatGoogleGenerativeAI`. Toda falha sai como `ProviderUnavailable`, ou `CircuitOpen`
com o circuito aberto, e nunca leva o texto do prompt.

Quem usa: `build_chat_provider` (`chat_factory`) com `APP_AI_ADAPTER=gemini` e a chave
configurada. O `AiRuntime` guarda uma instância por processo, então um circuito só para as
perguntas e o cadastro (seção 7.1). Os testes injetam um `ChatBackend` falso, um relógio e um
`sleep` que não espera.
"""

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
from app.adapters.tracing_scope import quiet_provider_tracing
from app.domain.errors import CircuitOpen, ProviderUnavailable
from app.ports.chat import Message, ModelT, RunContext, TokenUsage, Tool, ToolResult
from app.ports.clock import Clock
from app.prompts.qa import CHAT_UNAVAILABLE, CIRCUIT_OPEN_MESSAGE

# A primeira chamada e até duas novas tentativas, só em 429 e 503. A espera começa em 20 s e
# dobra a cada tentativa: 20 s e depois 40 s (seções 5.3 e 17).
CHAT_ATTEMPTS = 3
CHAT_RETRY_DELAY_SECONDS = 20.0
T = TypeVar("T")


class ChatBackend(Protocol):
    """A chamada crua ao modelo, sem resiliência. `LangChainChatBackend` é a implementação.

    Cada método devolve o valor junto com o `TokenUsage` daquela resposta, e o fluxo devolve
    pares de texto e uso a cada pedaço. A temperatura vem do `RunContext` de quem chama.
    """

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
    """O provedor de chat do Gemini, com tempo limite, novas tentativas e circuit breaker.

    Uma chamada que esgota as tentativas conta como uma falha só no circuito. O tempo limite
    não tem nova tentativa: pela seção 5.3, ela vale só para 429 e 503. `clock`, `sleep` e
    `backend` existem para os testes; sem `backend`, `_default_backend` monta o do LangChain.
    """

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
        # Um circuito por instância. O `AiRuntime` mantém a instância viva pelo processo; um
        # provedor novo por pedido zeraria a contagem de falhas (seção 7.1).
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
        """Saída estruturada: o modelo responde no schema Pydantic pedido.

        Soma os tokens da resposta em `run`. Levanta `CircuitOpen` com o circuito aberto e
        `ProviderUnavailable` em qualquer outra falha, inclusive uma resposta que não é do
        schema pedido.
        """
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
        """Chamada com ferramentas: devolve a primeira chamada de ferramenta, ou o texto.

        Soma os tokens em `run`. Os erros são os de `complete_structured`.
        """
        value, usage = await self._attempt(
            lambda: self._backend.complete_with_tools(messages, tools, run.temperature)
        )
        _add_usage(run, usage)
        return value

    def stream(self, messages: list[Message], run: RunContext) -> AsyncIterator[str]:
        """Transmite a resposta em pedaços de texto, somando os tokens em `run` a cada pedaço.

        Devolve o gerador assíncrono de `_stream`, e nada roda até alguém iterar. Os tokens
        já contados ficam em `run` mesmo se quem lê cancelar o fluxo no meio (seção 6.4).
        """
        return self._stream(messages, run)

    async def _stream(self, messages: list[Message], run: RunContext) -> AsyncIterator[str]:
        """Mantém o rastro automático desligado durante todo o fluxo (seção 18.4)."""
        with quiet_provider_tracing():
            async for text in self._stream_quietly(messages, run):
                yield text

    async def _stream_quietly(
        self,
        messages: list[Message],
        run: RunContext,
    ) -> AsyncIterator[str]:
        """O fluxo com as guardas.

        1. Recusa na hora se o circuito está aberto.
        2. Lê uma tentativa inteira, repassando cada pedaço com texto.
        3. Repete só se nenhum pedaço chegou e o status é 429 ou 503: depois do primeiro
           pedaço, o texto pode já ter ido ao visitante, e repetir duplicaria a resposta.
        4. No fim sem erro, registra sucesso no circuito; numa falha final, registra a falha.
        """
        # 1.
        self._refuse_if_open()
        delay = CHAT_RETRY_DELAY_SECONDS
        for attempt in range(1, CHAT_ATTEMPTS + 1):
            yielded = False
            try:
                # 2. Um pedaço sem texto, só com uso, também conta como chegado.
                async for text in self._read_attempt(messages, run):
                    yielded = True
                    if text:
                        yield text
            except TimeoutError as exc:
                self._record_provider_failure(exc)
                raise ProviderUnavailable(CHAT_UNAVAILABLE) from exc
            # Defensivo: um `CircuitOpen` vindo de dentro sobe sem contar como falha nova.
            except CircuitOpen:
                raise
            # `asyncio.CancelledError` herda de `BaseException`, não de `Exception`: o visitante
            # que fecha o fluxo não passa por aqui e não conta como falha do provedor.
            except Exception as exc:
                # 3.
                if not yielded and retryable_status(exc) and attempt < CHAT_ATTEMPTS:
                    await self._sleep(delay)
                    delay *= 2
                    continue
                self._record_provider_failure(exc)
                raise ProviderUnavailable(CHAT_UNAVAILABLE) from exc
            else:
                # 4.
                self._breaker.record_success()
                return
        # Inalcançável: a última tentativa sai pelo `raise` acima. A Etapa 13.5 remove estas
        # linhas mortas.
        self._breaker.record_failure()
        raise ProviderUnavailable(CHAT_UNAVAILABLE)

    async def _read_attempt(
        self,
        messages: list[Message],
        run: RunContext,
    ) -> AsyncIterator[str]:
        """Uma tentativa de fluxo, com prazo para o fluxo inteiro, não para cada pedaço.

        Cada espera usa só o que resta dos 120 s; esgotado o prazo, levanta `TimeoutError`.
        O uso de cada pedaço entra em `run` antes de o texto seguir, para a soma valer no meio
        de uma resposta cancelada (seção 7.1, "Orçamento e degradação").
        """
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
        """Roda `operation` com o rastro automático do LangChain desligado (seção 18.4)."""
        with quiet_provider_tracing():
            return await self._attempt_quietly(operation)

    async def _attempt_quietly(self, operation: Callable[[], Awaitable[T]]) -> T:
        """Uma chamada sem fluxo, com as guardas.

        1. Recusa na hora se o circuito está aberto.
        2. Dá a cada tentativa o prazo de `CHAT_TIMEOUT_SECONDS`; o tempo limite não repete.
        3. Repete em 429 e 503, com espera de 20 s que dobra a cada vez.
        4. Registra sucesso ou uma falha só no circuito, qualquer que seja o número de
           tentativas.
        """
        # 1.
        self._refuse_if_open()
        delay = CHAT_RETRY_DELAY_SECONDS
        last: BaseException | None = None
        for attempt in range(1, CHAT_ATTEMPTS + 1):
            try:
                # 2. `asyncio.timeout` cancela a operação quando o prazo acaba.
                async with asyncio.timeout(self._timeout):
                    result = await operation()
            except TimeoutError as exc:
                self._record_provider_failure(exc)
                raise ProviderUnavailable(CHAT_UNAVAILABLE) from exc
            # Defensivo: um `CircuitOpen` vindo de dentro sobe sem contar como falha nova.
            except CircuitOpen:
                raise
            except Exception as exc:
                last = exc
                # 3. Uma resposta ilegível (`ChatResponseError`) não tem status e não repete.
                if retryable_status(exc) and attempt < CHAT_ATTEMPTS:
                    await self._sleep(delay)
                    delay *= 2
                    continue
                self._record_provider_failure(exc)
                raise ProviderUnavailable(CHAT_UNAVAILABLE) from exc
            else:
                # 4.
                self._breaker.record_success()
                return result
        # Inalcançável: a última tentativa sai pelo `raise` acima. A Etapa 13.5 remove estas
        # linhas mortas.
        self._breaker.record_failure()
        raise ProviderUnavailable(CHAT_UNAVAILABLE) from last

    def _refuse_if_open(self) -> None:
        """Levanta `CircuitOpen` sem chamar o modelo enquanto o circuito estiver aberto."""
        if not self._breaker.allow():
            raise CircuitOpen(CIRCUIT_OPEN_MESSAGE)

    def _record_provider_failure(self, exc: BaseException) -> None:
        """Conta a falha no circuito e registra o log `chat.provider_failed`.

        O log leva só o tipo da exceção e o status HTTP, nunca a mensagem: ela pode repetir o
        prompt ou o corpo da resposta.
        """
        self._breaker.record_failure()
        structlog.get_logger("atrium").warning(
            "chat.provider_failed",
            error_type=type(exc).__name__,
            status_code=http_status(exc),
        )


def _default_backend(*, api_key: str, model: str, timeout_seconds: float) -> ChatBackend:
    """O backend do LangChain, montado só quando nenhum backend foi injetado.

    O `langchain_google_genai` só é importado dentro de `build_langchain_model`. O modelo
    nasce com temperatura 0, e o backend faz uma cópia quando a chamada pede outra.
    """
    from app.adapters.langchain_chat import LangChainChatBackend, build_langchain_model

    built = build_langchain_model(
        model=model,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        temperature=0,
    )
    return LangChainChatBackend(built)


def _add_usage(run: RunContext, usage: TokenUsage) -> None:
    """Soma o uso de uma resposta, ou de um pedaço do fluxo, no `RunContext` da chamada."""
    run.input_tokens += usage.input_tokens
    run.output_tokens += usage.output_tokens


async def _next_chunk(
    iterator: AsyncIterator[tuple[str, TokenUsage]],
) -> tuple[str, TokenUsage] | None:
    """O próximo pedaço do fluxo, ou `None` no fim.

    Dentro de um gerador assíncrono, um `StopAsyncIteration` que escapa vira `RuntimeError`
    (PEP 479). Devolver `None` deixa `_read_attempt` terminar com um `return` normal.
    """
    try:
        return await anext(iterator)
    except StopAsyncIteration:
        return None
