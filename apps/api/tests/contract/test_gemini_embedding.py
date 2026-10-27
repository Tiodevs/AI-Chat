"""Um texto por pedido HTTP, 768 dimensões, 429 e no máximo 4 simultâneos. Seção 17."""

import asyncio
import json

import httpx

from app.adapters.gemini_embedding import GeminiEmbeddingProvider

_DIMENSIONS = 768


def test_each_text_is_one_request_and_one_vector() -> None:
    recorded: list[dict[str, object]] = []

    class Transport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            recorded.append(json.loads(request.content.decode()))
            assert request.url.path.endswith(":embedContent")
            assert request.headers["x-goog-api-key"] == "test-key"
            return httpx.Response(200, json={"embedding": {"values": [0.1] * _DIMENSIONS}})

    provider = _provider(Transport())
    texts = ["um", "dois", "três", "quatro", "cinco"]
    vectors = asyncio.run(provider.embed_documents(texts))
    assert len(recorded) == len(texts)
    assert len(vectors) == len(texts)
    assert [len(vector) for vector in vectors] == [_DIMENSIONS] * len(texts)
    sent = [body["content"] for body in recorded]
    assert sent == [{"parts": [{"text": text}]} for text in texts]
    assert {body["outputDimensionality"] for body in recorded} == {_DIMENSIONS}


def test_a_429_is_retried() -> None:
    calls = 0
    slept: list[float] = []

    class Transport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(429, json={"error": "rate"})
            return httpx.Response(200, json={"embedding": {"values": [0.2] * _DIMENSIONS}})

    async def sleep(delay: float) -> None:
        slept.append(delay)

    provider = _provider(Transport(), sleep=sleep)
    vector = asyncio.run(provider.embed_query("visita"))
    assert calls == 2
    assert slept == [0.5]
    assert len(vector) == _DIMENSIONS


def test_at_most_four_requests_are_in_flight() -> None:
    in_flight = 0
    max_in_flight = 0

    class Transport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            nonlocal in_flight, max_in_flight
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
            await asyncio.sleep(0)
            in_flight -= 1
            return httpx.Response(200, json={"embedding": {"values": [0.3] * _DIMENSIONS}})

    provider = _provider(Transport())
    vectors = asyncio.run(provider.embed_documents([str(index) for index in range(8)]))
    assert len(vectors) == 8
    assert max_in_flight == 4


def _provider(
    transport: httpx.AsyncBaseTransport,
    sleep: object | None = None,
) -> GeminiEmbeddingProvider:
    client = httpx.AsyncClient(transport=transport)
    if sleep is None:
        return GeminiEmbeddingProvider(
            api_key="test-key",
            model="gemini-embedding-2",
            dimensions=_DIMENSIONS,
            client=client,
        )
    return GeminiEmbeddingProvider(
        api_key="test-key",
        model="gemini-embedding-2",
        dimensions=_DIMENSIONS,
        client=client,
        sleep=sleep,  # type: ignore[arg-type]
    )
