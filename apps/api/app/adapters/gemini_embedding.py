"""Um pedido HTTP embedContent por texto. Seção 17 do SDD.

Adaptador da porta `EmbeddingProvider` (`app.ports.embedding`) que chama a API Gemini direto
pelo `httpx`, sem LangChain. O contrato da seção 17: o `gemini-embedding-2` agrega num único
embedding várias entradas enviadas juntas, então cada texto vai num pedido próprio, com no
máximo 4 pedidos simultâneos e nova tentativa em 429. O teste de contrato
`tests/contract/test_gemini_embedding.py` confere isso com HTTP simulado.

Quem usa: `build_embedding_provider` com `APP_AI_ADAPTER=gemini` e a chave configurada, para a
pergunta (`QaWorkflow`), a ingestão e a semente.

Diferenças em relação ao chat, que a Etapa 13.2 corrige: os erros de rede do `httpx`
(`TimeoutException`, `ConnectError`) escapam sem virar `EmbeddingRequestError`, o 503 não tem
nova tentativa, não há circuit breaker e o cliente HTTP é criado a cada chamada quando não vem
injetado.
"""

import asyncio
from collections.abc import Awaitable, Callable
from urllib.parse import quote

import httpx

from app.models.vector import EMBEDDING_DIMENSIONS

# Seções 6.4 e 17: no máximo 4 pedidos de embedding ao mesmo tempo, por instância.
_MAX_CONCURRENCY = 4
# A primeira chamada e até duas novas tentativas em 429, com espera de 0,5 s que dobra.
_ATTEMPTS = 3
_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class _ClientScope:
    """Context manager que fecha o cliente HTTP só quando foi criado aqui.

    Um cliente injetado, como o dos testes, continua aberto para quem o passou.
    """

    def __init__(self, client: httpx.AsyncClient, *, close: bool) -> None:
        self._client = client
        self._close = close

    async def __aenter__(self) -> httpx.AsyncClient:
        return self._client

    async def __aexit__(self, *_exc: object) -> None:
        if self._close:
            await self._client.aclose()


class EmbeddingRequestError(Exception):
    """Falha do provedor sem o texto enviado nem a chave.

    A mensagem leva só o status ou o problema da resposta. O `QaWorkflow` a converte no
    desfecho `error`; a ingestão marca a versão como `failed`. A Etapa 13.2 a move para
    `app.ports.embedding` ou `app.domain.errors`, porque um workflow não deveria importar um
    adaptador.
    """


class GeminiEmbeddingProvider:
    """Embeddings do Gemini, um texto por pedido, com o tamanho do vetor conferido.

    `model` aceita o nome com ou sem o prefixo `models/`. `client` e `sleep` existem para os
    testes. O semáforo vale por instância: o `QaWorkflow` usa uma pelo processo inteiro, e o
    serviço de documentos do admin cria uma por pedido.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimensions: int = EMBEDDING_DIMENSIONS,
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.model_name = model
        self.dimensions = dimensions
        self._api_key = api_key
        self._client = client
        self._sleep = sleep
        self._semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)
        # `quote` com `safe=""` impede que o nome do modelo mude o caminho da URL.
        model_name = quote(model.removeprefix("models/"), safe="")
        self._url = f"{_BASE_URL}/{model_name}:embedContent"

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Um vetor por texto, na ordem recebida, com um pedido HTTP por texto (seção 17).

        `asyncio.gather` dispara os pedidos juntos e devolve os resultados na ordem dos
        textos; o semáforo deixa no máximo 4 em voo. A primeira falha sobe para quem chamou.
        """
        async with self._open_client() as client:
            return list(await asyncio.gather(*(self._limited(client, text) for text in texts)))

    async def embed_query(self, text: str) -> list[float]:
        """O vetor de um texto só. O prefixo da seção 8.3 vem pronto de quem chama."""
        async with self._open_client() as client:
            return await self._limited(client, text)

    async def _limited(self, client: httpx.AsyncClient, text: str) -> list[float]:
        """Espera uma vaga no semáforo e embeda um texto."""
        async with self._semaphore:
            return await self._embed_one(client, text)

    async def _embed_one(self, client: httpx.AsyncClient, text: str) -> list[float]:
        """Um pedido `embedContent` com `outputDimensionality`, repetido em 429.

        A chave vai no cabeçalho `x-goog-api-key`, nunca na URL, que o `httpx` escreve no log
        de cada pedido. Um status diferente de 200 levanta `EmbeddingRequestError` com o número
        do status. Um vetor de tamanho diferente de `dimensions` também levanta, porque a coluna
        é `vector(768)` (seção 8.3).
        """
        delay = 0.5
        for attempt in range(1, _ATTEMPTS + 1):
            response = await client.post(
                self._url,
                headers={"x-goog-api-key": self._api_key},
                json={
                    "content": {"parts": [{"text": text}]},
                    "outputDimensionality": self.dimensions,
                },
            )
            if response.status_code == 429 and attempt < _ATTEMPTS:
                await self._sleep(delay)
                delay *= 2
                continue
            if response.status_code != 200:
                raise EmbeddingRequestError(f"embedding status {response.status_code}")
            return _vector(response.json(), self.dimensions)
        # Inalcançável: na última tentativa, um 429 sai pelo `raise` de status acima.
        raise EmbeddingRequestError("embedding status 429")

    def _open_client(self) -> _ClientScope:
        """O cliente injetado, que fica aberto, ou um novo de 30 s, fechado no fim da chamada."""
        if self._client is not None:
            return _ClientScope(self._client, close=False)
        return _ClientScope(httpx.AsyncClient(timeout=30.0), close=True)


def _vector(payload: object, dimensions: int) -> list[float]:
    """O vetor de uma resposta `{"embedding": {"values": [...]}}`, conferido no tamanho."""
    if not isinstance(payload, dict):
        raise EmbeddingRequestError("embedding response")
    embedding = payload.get("embedding")
    if not isinstance(embedding, dict):
        raise EmbeddingRequestError("embedding response")
    values = embedding.get("values")
    if not isinstance(values, list) or len(values) != dimensions:
        raise EmbeddingRequestError("embedding dimensions")
    return [float(value) for value in values]
