"""ChatGoogleGenerativeAI atrás da porta de chat. Seção 17 do SDD.

Adaptador (seção 6.2): a única peça que fala com o LangChain no caminho do chat. Implementa o
protocolo `ChatBackend` de `gemini_chat`, que põe por cima o tempo limite, as novas tentativas
e o circuit breaker. Aqui ficam só a tradução das mensagens da porta para o formato do
LangChain e a leitura da resposta: texto, saída estruturada, chamada de ferramenta e tokens.

Quem usa: `GeminiChatProvider`, por `_default_backend`. Os testes de `test_qa_provider`
exercitam o backend e as funções de leitura sem rede.
"""

from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel

from app.ports.chat import Message, TokenUsage, Tool, ToolResult

# Seções 5.3 e 17: 120 s por chamada. O valor vai ao SDK como `timeout` e ao provedor, que
# põe o mesmo prazo em volta de cada tentativa.
CHAT_TIMEOUT_SECONDS = 120.0
# O SDK não repete por conta própria: as novas tentativas são do `GeminiChatProvider`, para
# não repetir por cima do circuito (seção 17).
SDK_MAX_RETRIES = 0
# Sem orçamento de "pensamento": o pensamento padrão do `gemini-3.8-flash` consome o prazo e a
# API devolve 504 (seção 17).
THINKING_BUDGET = 0


class ChatResponseError(Exception):
    """A resposta do modelo não pôde ser lida. Sem texto de prompt.

    A mensagem diz só o tipo de chamada (`structured` ou `tool`). O `GeminiChatProvider` a
    converte em `ProviderUnavailable`, sem nova tentativa, e a conta como falha no circuito.
    """


class LangChainChatBackend:
    """Implementa `ChatBackend` com um modelo de chat do LangChain.

    Um Runnable é a interface comum do LangChain para o que recebe uma entrada e devolve uma
    saída, com `ainvoke` e `astream`. `with_structured_output` e `bind_tools` devolvem
    Runnables novos em volta do modelo, sem mudar o original. Cada método devolve o valor junto
    com o `TokenUsage` lido da mensagem do modelo.
    """

    def __init__(self, model: Any) -> None:
        self._model = model

    async def complete_structured(
        self,
        messages: list[Message],
        schema: type[BaseModel],
        temperature: float,
    ) -> tuple[BaseModel, TokenUsage]:
        """Saída estruturada: o modelo responde num JSON que segue o schema Pydantic.

        Com `include_raw=True`, o Runnable devolve um `dict` com `raw` (a mensagem do modelo),
        `parsed` (a instância do schema) e `parsing_error`. A mensagem crua é a que traz o uso
        de tokens. Levanta `ChatResponseError` quando a saída não pôde ser lida.
        """
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
        """Chamada com ferramentas: `bind_tools` anexa as declarações de função ao pedido.

        Devolve a primeira chamada de ferramenta da resposta, ou o texto quando o modelo não
        chamou nenhuma, e o uso de tokens.
        """
        model = self._at(temperature)
        bound = model.bind_tools([_tool_spec(tool) for tool in tools])
        message = await bound.ainvoke(_to_langchain(messages), temperature=temperature)
        return _tool_result(message), message_usage(message)

    def stream(
        self,
        messages: list[Message],
        temperature: float,
    ) -> AsyncIterator[tuple[str, TokenUsage]]:
        """Fluxo da resposta em pares de texto e uso. Devolve o gerador de `_stream`."""
        return self._stream(messages, temperature)

    async def _stream(
        self,
        messages: list[Message],
        temperature: float,
    ) -> AsyncIterator[tuple[str, TokenUsage]]:
        """Lê `astream` pedaço a pedaço.

        O Gemini manda o uso acumulado em cada pedaço, e o `langchain_google_genai` o converte
        na diferença desde o pedaço anterior. Por isso somar o uso dos pedaços dá o total.
        """
        model = self._at(temperature)
        async for chunk in model.astream(_to_langchain(messages), temperature=temperature):
            yield message_text(chunk), message_usage(chunk)

    def _at(self, temperature: float) -> Any:
        """O modelo com a temperatura pedida.

        Reaproveita o modelo quando a temperatura já é a mesma. Senão, `model_copy` faz uma
        cópia Pydantic com a temperatura nova e o resto da configuração, como o tempo limite
        e o thinking budget.
        """
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
    """Cria o `ChatGoogleGenerativeAI` com a configuração da seção 17.

    `vertexai=False` usa a API Gemini com chave de API, não a Vertex AI. O import fica aqui
    dentro para o `langchain_google_genai` carregar só quando o provedor real nasce.
    """
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
    """O texto de uma mensagem do LangChain.

    O conteúdo pode ser uma `str` ou uma lista de blocos, como o Gemini devolve; dos blocos,
    entram as strings e o campo `text` dos dicionários. O resto vira texto vazio.
    """
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
    """Os tokens de `usage_metadata`, o formato de uso padrão do LangChain. Sem ele, zero."""
    raw = getattr(message, "usage_metadata", None)
    if not isinstance(raw, dict):
        return TokenUsage()
    return TokenUsage(
        input_tokens=_count(raw.get("input_tokens")),
        output_tokens=_count(raw.get("output_tokens")),
    )


def _parse_structured(payload: object, schema: type[BaseModel]) -> BaseModel:
    """A instância do schema a partir da saída com `include_raw`.

    Um `parsing_error` ou uma saída que não é do schema levanta `ChatResponseError`. Um
    `parsed` que veio como `dict` é validado pelo Pydantic.
    """
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
    """O uso da mensagem crua, ou zero quando ela não veio."""
    if message is None:
        return TokenUsage()
    return message_usage(message)


def _tool_result(message: object) -> ToolResult:
    """A primeira chamada de ferramenta da mensagem, como `ToolResult` da porta.

    Sem chamada, devolve nome vazio e o texto da resposta; o cadastro trata isso como saída
    rejeitada. Uma chamada sem nome em texto ou sem argumentos em `dict` levanta
    `ChatResponseError`. As chaves dos argumentos viram `str`; os valores passam como vieram,
    para a lista de permissão do domínio julgar.
    """
    calls = getattr(message, "tool_calls", None)
    if not isinstance(calls, list) or not calls:
        return ToolResult(name="", arguments={}, text=message_text(message).strip())
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
    """A ferramenta da porta no formato de função que o `bind_tools` aceita.

    O LangChain converte este formato para a declaração de função do Gemini.
    """
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def _to_langchain(messages: list[Message]) -> list[tuple[str, str]]:
    """As mensagens da porta como pares `(papel, texto)`, que o LangChain aceita.

    Os papéis do LangChain são `system`, `human` e `ai`.
    """
    roles = {"system": "system", "user": "human", "assistant": "ai"}
    return [(roles[message.role], message.content) for message in messages]


def _count(value: object) -> int:
    """Uma contagem de tokens não negativa. `bool` é subclasse de `int`, então é recusado."""
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(value, 0)
