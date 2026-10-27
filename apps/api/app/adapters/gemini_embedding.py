"""Um pedido HTTP embedContent por texto. Seção 17 do SDD."""

import asyncio
from collections.abc import Awaitable, Callable
from urllib.parse import quote

import httpx

from app.models.vector import EMBEDDING_DIMENSIONS

_MAX_CONCURRENCY = 4
_ATTEMPTS = 3
_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class _ClientScope:
    def __init__(self, client: httpx.AsyncClient, *, close: bool) -> None:
        self._client = client
        self._close = close

    async def __aenter__(self) -> httpx.AsyncClient:
        return self._client

    async def __aexit__(self, *_exc: object) -> None:
        if self._close:
            await self._client.aclose()


class EmbeddingRequestError(Exception):
    """Falha do provedor sem o texto enviado nem a chave."""


class GeminiEmbeddingProvider:
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
        model_name = quote(model.removeprefix("models/"), safe="")
        self._url = f"{_BASE_URL}/{model_name}:embedContent"

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        async with self._open_client() as client:
            return list(await asyncio.gather(*(self._limited(client, text) for text in texts)))

    async def embed_query(self, text: str) -> list[float]:
        async with self._open_client() as client:
            return await self._limited(client, text)

    async def _limited(self, client: httpx.AsyncClient, text: str) -> list[float]:
        async with self._semaphore:
            return await self._embed_one(client, text)

    async def _embed_one(self, client: httpx.AsyncClient, text: str) -> list[float]:
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
        raise EmbeddingRequestError("embedding status 429")

    def _open_client(self) -> _ClientScope:
        if self._client is not None:
            return _ClientScope(self._client, close=False)
        return _ClientScope(httpx.AsyncClient(timeout=30.0), close=True)


def _vector(payload: object, dimensions: int) -> list[float]:
    if not isinstance(payload, dict):
        raise EmbeddingRequestError("embedding response")
    embedding = payload.get("embedding")
    if not isinstance(embedding, dict):
        raise EmbeddingRequestError("embedding response")
    values = embedding.get("values")
    if not isinstance(values, list) or len(values) != dimensions:
        raise EmbeddingRequestError("embedding dimensions")
    return [float(value) for value in values]
