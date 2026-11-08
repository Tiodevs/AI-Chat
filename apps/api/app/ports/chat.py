"""Porta de chat. Seção 17 do SDD.

Camada de portas. `QaWorkflow`, `RegistrationWorkflow` e o juiz de fundamentação de
`app/evals/evaluators.py` chamam um `ChatProvider`. Os adaptadores são `GeminiChatProvider`
(produção), `FakeChatProvider` (testes, com respostas escritas no teste), `DemoChatProvider`
(`APP_AI_ADAPTER=demo`) e `UnavailableChatProvider` (sem `GEMINI_API_KEY`), escolhidos por
`build_chat_provider` (`app/adapters/chat_factory.py`).

Os tipos daqui são neutros: nenhum vem do LangChain. O backend do Gemini traduz `Message`,
`Tool` e `ToolResult` para os tipos do LangChain, e o workflow nunca vê esses tipos.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal, Protocol, TypeVar
from uuid import UUID

from pydantic import BaseModel

# Tipo do schema da saída estruturada: `complete_structured(..., schema=X, ...)` devolve um `X`.
ModelT = TypeVar("ModelT", bound=BaseModel)
# Política de rastro do passo (seção 18.4). `app/domain/trace_policy.py` declara o mesmo
# `Literal`.
TracePolicy = Literal["full", "masked", "metadata_only"]
# Papel de uma mensagem. `system` leva as instruções do prompt.
MessageRole = Literal["system", "user", "assistant"]


@dataclass(frozen=True, slots=True)
class Message:
    """Uma mensagem da conversa com o modelo, na ordem em que vai."""

    role: MessageRole
    content: str


@dataclass(frozen=True, slots=True)
class Tool:
    """Uma ferramenta que o modelo pode chamar. O cadastro usa uma só, `set_fields`.

    `parameters` é o JSON Schema dos argumentos.
    """

    name: str
    description: str
    parameters: dict[str, object]


@dataclass(frozen=True, slots=True)
class ToolResult:
    """O que o modelo devolveu numa chamada com ferramenta.

    `name` é a ferramenta chamada, ou vazio quando o modelo só respondeu texto. `arguments`
    ainda não foram validados: quem valida é o domínio (`fields.read_tool_arguments`). `text` é
    o texto que veio junto.
    """

    name: str
    arguments: dict[str, object]
    text: str = ""


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Tokens de uma chamada ou de um pedaço do fluxo, como o backend do LangChain informa.

    `GeminiChatProvider` soma cada `TokenUsage` no `RunContext` da chamada.
    """

    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(slots=True)
class RunContext:
    """Temperatura da chamada e tokens preenchidos pelo adaptador. Seção 17 do SDD.

    Quem chama preenche os campos de cima, e o adaptador soma `input_tokens` e `output_tokens`
    a cada resposta ou pedaço do fluxo. Por isso a classe não é imutável.

    - `run_id`: id do run no LangSmith. Na pergunta, é o id da mensagem do assistente.
    - `request_id`: o do pedido HTTP, que liga log, rastro e mensagem (seção 18).
    - `prompt_version`: a versão do prompt usado.
    - `trace_policy`: quanto o passo pode mandar ao LangSmith.
    - `temperature`: 0 na classificação e na extração, 0,2 na resposta e na frase (seção 10.2).

    Nenhum adaptador lê `trace_policy`, `tags`, `request_id` nem `prompt_version`: o
    `GeminiChatProvider` usa só `temperature` e desliga o rastreamento automático em volta da
    chamada. A política vale nos rastros explícitos de `app/domain/trace_policy.py`. A seção 17
    diz que os adaptadores traduzem o contexto para a configuração do LangChain; o código não
    faz essa tradução.
    """

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

    O `QaWorkflow` registra aqui cada chamada da pergunta. O `ConversationService` cria a
    contagem e lê o total para o orçamento, inclusive quando a resposta não chega ao fim.
    """

    runs: list[RunContext] = field(default_factory=list)

    def track(self, run: RunContext) -> RunContext:
        """Registra o contexto e o devolve, para quem chama usá-lo na mesma expressão."""
        self.runs.append(run)
        return run

    @property
    def input_tokens(self) -> int:
        """Soma dos tokens de entrada de todas as chamadas registradas."""
        return sum(run.input_tokens for run in self.runs)

    @property
    def output_tokens(self) -> int:
        """Soma dos tokens de saída de todas as chamadas registradas."""
        return sum(run.output_tokens for run in self.runs)


class ChatProvider(Protocol):
    """O modelo de chat visto pelos workflows.

    Três formas de chamar, cada uma com um `RunContext` que o adaptador preenche com os
    tokens:

    - `complete_structured`: resposta num schema Pydantic. Reescrita da pergunta, frase do
      cadastro e juiz de fundamentação.
    - `complete_with_tools`: chamada que pode usar ferramenta. Extração do cadastro.
    - `stream`: texto em pedaços. Geração da resposta ao visitante.

    Erros: `ProviderUnavailable` numa falha do provedor e `CircuitOpen` com o circuito aberto,
    ambos de `app/domain/errors.py`.
    """

    # Nome do modelo. Vai para `messages.model`, para os spans e para as métricas de tokens.
    model_name: str

    async def complete_structured(
        self,
        messages: list[Message],
        schema: type[ModelT],
        run: RunContext,
    ) -> ModelT:
        """Pede a resposta no formato de `schema` e devolve a instância validada.

        Levanta `ProviderUnavailable` quando o modelo falha ou devolve algo fora do schema.
        """
        ...

    async def complete_with_tools(
        self,
        messages: list[Message],
        tools: list[Tool],
        run: RunContext,
    ) -> ToolResult:
        """Oferece as ferramentas ao modelo e devolve a chamada que ele fez.

        Sem chamada de ferramenta, o `ToolResult` vem com o nome vazio.
        """
        ...

    def stream(self, messages: list[Message], run: RunContext) -> AsyncIterator[str]:
        """Devolve os pedaços de texto da resposta conforme chegam.

        Não é `async def`: devolve um iterador assíncrono, que quem chama percorre com
        `async for`. Os tokens entram no `run` a cada pedaço, então o uso vale mesmo se o fluxo
        for cancelado no meio (seção 6.4).
        """
        ...
