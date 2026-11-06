"""Provedores sem chave do Gemini. Seções 10.1, 17 e 22.1 do SDD.

Com `APP_AI_ADAPTER=gemini` e `GEMINI_API_KEY` vazia, montar o cliente do Gemini falhava na
injeção de dependência e derrubava com 500 toda rota que usa o workflow, até o fluxo de
diagnóstico. Estes provedores falham só na chamada, como provedor indisponível: a pergunta
recebe a resposta fixa de indisponibilidade, o cadastro oferece o formulário e a ingestão
marca a versão como falha, sem pedidos de rede inúteis.
"""

from collections.abc import AsyncIterator

from app.adapters.gemini_embedding import EmbeddingRequestError
from app.domain.errors import ProviderUnavailable
from app.ports.chat import Message, ModelT, RunContext, Tool, ToolResult
from app.prompts.qa import CHAT_UNAVAILABLE


class UnavailableChatProvider:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    async def complete_structured(
        self,
        messages: list[Message],
        schema: type[ModelT],
        run: RunContext,
    ) -> ModelT:
        raise ProviderUnavailable(CHAT_UNAVAILABLE)

    async def complete_with_tools(
        self,
        messages: list[Message],
        tools: list[Tool],
        run: RunContext,
    ) -> ToolResult:
        raise ProviderUnavailable(CHAT_UNAVAILABLE)

    def stream(self, messages: list[Message], run: RunContext) -> AsyncIterator[str]:
        async def iterate() -> AsyncIterator[str]:
            raise ProviderUnavailable(CHAT_UNAVAILABLE)
            yield ""  # pragma: no cover - torna a função um gerador assíncrono

        return iterate()


class UnavailableEmbeddingProvider:
    def __init__(self, *, model_name: str, dimensions: int) -> None:
        self.model_name = model_name
        self.dimensions = dimensions

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingRequestError("GEMINI_API_KEY ausente")

    async def embed_query(self, text: str) -> list[float]:
        raise EmbeddingRequestError("GEMINI_API_KEY ausente")
