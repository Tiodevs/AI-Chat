"""Chat falso para testes. Seção 17 do SDD.

Implementa a porta `ChatProvider` sem rede (ADR-004, NFR-3). O teste escreve o roteiro: a saída
estruturada, os tokens do fluxo e a chamada de ferramenta, ou uma exceção no lugar de cada um.
O falso guarda cada chamada recebida, para o teste conferir mensagens, ferramentas e
temperatura.

Quem usa: os testes de unidade e de integração, que o injetam explicitamente, e
`build_chat_provider` com `APP_AI_ADAPTER=fake`, sem roteiro. Sem roteiro, toda chamada falha
como provedor indisponível, e toda pergunta recebe a resposta de indisponibilidade (seção 17).
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence

from pydantic import BaseModel

from app.domain.errors import ProviderUnavailable
from app.ports.chat import Message, ModelT, RunContext, Tool, ToolResult
from app.prompts.qa import CHAT_UNAVAILABLE


class FakeChatProvider:
    """Respostas escritas no teste, com contagem de tokens programável.

    `structured`, `tokens` e `tool_result` aceitam o valor ou uma exceção, que a chamada
    levanta (por exemplo `ProviderUnavailable` ou `CircuitOpen`). Os pares de uso somam
    `(entrada, saída)` no `RunContext`. `stream_hook` roda antes do primeiro token, para o
    teste agir no começo do fluxo. `pause_after` para o fluxo depois de N tokens até o teste
    marcar `released`, para simular um cancelamento no meio. As listas `structured_calls`,
    `stream_calls` e `tool_calls` guardam o que cada chamada recebeu.
    """

    def __init__(
        self,
        *,
        structured: BaseModel | Exception | None = None,
        tokens: Sequence[str] | Exception | None = None,
        tool_result: ToolResult | Exception | None = None,
        structured_usage: tuple[int, int] = (0, 0),
        stream_usage: tuple[int, int] = (0, 0),
        tool_usage: tuple[int, int] = (0, 0),
        token_usage: tuple[int, int] = (0, 0),
        model_name: str = "fake-chat",
        stream_hook: Callable[[], Awaitable[None]] | None = None,
        pause_after: int | None = None,
    ) -> None:
        """`token_usage` entra a cada token do fluxo, como os pedaços do Gemini.

        `stream_usage` entra só no fim, quando o fluxo termina sem cancelamento.
        """
        self.model_name = model_name
        self.structured_calls: list[tuple[tuple[Message, ...], RunContext]] = []
        self.stream_calls: list[tuple[tuple[Message, ...], RunContext]] = []
        self.tool_calls: list[tuple[tuple[Message, ...], tuple[Tool, ...], RunContext]] = []
        self.paused = asyncio.Event()
        self.released = asyncio.Event()
        self._structured = structured
        self._tokens = tokens
        self._tool_result = tool_result
        self._structured_usage = structured_usage
        self._stream_usage = stream_usage
        self._tool_usage = tool_usage
        self._token_usage = token_usage
        self._stream_hook = stream_hook
        self._pause_after = pause_after

    def script(
        self,
        *,
        structured: BaseModel | Exception | None = None,
        tokens: Sequence[str] | Exception | None = None,
        tool_result: ToolResult | Exception | None = None,
    ) -> None:
        """Troca o roteiro entre chamadas. Um argumento `None` mantém o roteiro anterior."""
        if structured is not None:
            self._structured = structured
        if tokens is not None:
            self._tokens = tokens
        if tool_result is not None:
            self._tool_result = tool_result

    async def complete_structured(
        self,
        messages: list[Message],
        schema: type[ModelT],
        run: RunContext,
    ) -> ModelT:
        """Devolve `structured` quando ele é do schema pedido; senão, indisponível."""
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
        """Devolve `tool_result` quando há um; senão, indisponível."""
        self.tool_calls.append((tuple(messages), tuple(tools), run))
        if isinstance(self._tool_result, Exception):
            raise self._tool_result
        run.input_tokens += self._tool_usage[0]
        run.output_tokens += self._tool_usage[1]
        if isinstance(self._tool_result, ToolResult):
            return self._tool_result
        raise ProviderUnavailable(CHAT_UNAVAILABLE)

    def stream(self, messages: list[Message], run: RunContext) -> AsyncIterator[str]:
        """Transmite `tokens` um a um, somando `token_usage` antes de cada um.

        Sem `tokens`, o fluxo termina vazio. Com `pause_after`, marca `paused` depois de N
        tokens e espera `released` por até 3 s; passado o prazo, falha como indisponível, para
        um teste travado falhar em vez de ficar parado.
        """

        async def iterate() -> AsyncIterator[str]:
            self.stream_calls.append((tuple(messages), run))
            if self._stream_hook is not None:
                await self._stream_hook()
            if isinstance(self._tokens, Exception):
                raise self._tokens
            for sent, token in enumerate(self._tokens or (), start=1):
                run.input_tokens += self._token_usage[0]
                run.output_tokens += self._token_usage[1]
                yield token
                if self._pause_after is not None and sent >= self._pause_after:
                    self.paused.set()
                    try:
                        await asyncio.wait_for(self.released.wait(), timeout=3)
                    except TimeoutError as exc:
                        raise ProviderUnavailable(CHAT_UNAVAILABLE) from exc
            # Só chega aqui o fluxo lido até o fim; um cancelamento não soma este uso.
            run.input_tokens += self._stream_usage[0]
            run.output_tokens += self._stream_usage[1]

        return iterate()
