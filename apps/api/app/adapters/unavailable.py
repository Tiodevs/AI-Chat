"""Provedores sem chave do Gemini. Seções 10.1, 17 e 22.1 do SDD.

Com `APP_AI_ADAPTER=gemini` e `GEMINI_API_KEY` vazia, montar o cliente do Gemini falhava na
injeção de dependência e derrubava com 500 toda rota que usa o workflow, até o fluxo de
diagnóstico. Estes provedores falham só na chamada, como provedor indisponível: a pergunta
recebe a resposta fixa de indisponibilidade, o cadastro oferece o formulário e a ingestão
marca a versão como falha, sem pedidos de rede inúteis.

Quem usa: `build_chat_provider` e `build_embedding_provider`, quando falta a chave. É o estado
do primeiro deploy na Railway, antes de a chave existir (seção 22.1).
"""

from collections.abc import AsyncIterator

from app.adapters.gemini_embedding import EmbeddingRequestError
from app.domain.errors import ProviderUnavailable
from app.ports.chat import Message, ModelT, RunContext, Tool, ToolResult
from app.prompts.qa import CHAT_UNAVAILABLE


class UnavailableChatProvider:
    """Porta de chat que levanta `ProviderUnavailable` em toda chamada.

    Não tem circuit breaker: toda chamada falha na hora. A pergunta sai com desfecho `error` e
    o texto de indisponibilidade, e o cadastro por chat responde 503.
    """

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    async def complete_structured(
        self,
        messages: list[Message],
        schema: type[ModelT],
        run: RunContext,
    ) -> ModelT:
        """Sempre falha como provedor indisponível."""
        raise ProviderUnavailable(CHAT_UNAVAILABLE)

    async def complete_with_tools(
        self,
        messages: list[Message],
        tools: list[Tool],
        run: RunContext,
    ) -> ToolResult:
        """Sempre falha como provedor indisponível."""
        raise ProviderUnavailable(CHAT_UNAVAILABLE)

    def stream(self, messages: list[Message], run: RunContext) -> AsyncIterator[str]:
        """Um fluxo que falha no primeiro `__anext__`, como um fluxo de verdade falharia."""

        async def iterate() -> AsyncIterator[str]:
            raise ProviderUnavailable(CHAT_UNAVAILABLE)
            yield ""  # pragma: no cover - torna a função um gerador assíncrono

        return iterate()


class UnavailableEmbeddingProvider:
    """Porta de embedding que levanta `EmbeddingRequestError` em toda chamada.

    É o mesmo erro do adaptador do Gemini, então o pipeline grava `error` e a ingestão marca
    a versão como `failed`.
    """

    def __init__(self, *, model_name: str, dimensions: int) -> None:
        self.model_name = model_name
        self.dimensions = dimensions

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Sempre falha, sem pedido de rede."""
        raise EmbeddingRequestError("GEMINI_API_KEY ausente")

    async def embed_query(self, text: str) -> list[float]:
        """Sempre falha, sem pedido de rede."""
        raise EmbeddingRequestError("GEMINI_API_KEY ausente")
