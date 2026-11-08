"""Um texto por pedido HTTP, 768 dimensões, 429 e no máximo 4 simultâneos. Seção 17.

Teste de contrato do `GeminiEmbeddingProvider` (`app/adapters/gemini_embedding.py`). O contrato
existe porque o `gemini-embedding-2` agrega num único vetor várias entradas enviadas juntas
(seções 17 e 25): N textos têm de virar N pedidos e N vetores. Cada teste injeta um
`httpx.AsyncClient` com um transporte falso, então nenhum pedido sai da máquina e nenhuma chave
real é usada (NFR-3). A espera entre tentativas também é falsa, para o teste não dormir. Não
usa banco.
"""

import asyncio
import json

import httpx

from app.adapters.gemini_embedding import GeminiEmbeddingProvider

# A dimensão da coluna `vector(768)` e de `EMBEDDING_DIMENSIONS` (seção 8.3).
_DIMENSIONS = 768


def test_each_text_is_one_request_and_one_vector() -> None:
    recorded: list[dict[str, object]] = []

    class Transport(httpx.AsyncBaseTransport):
        """Grava o corpo de cada pedido e responde um vetor de 768 dimensões."""

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
        """Responde 429 no primeiro pedido e um vetor a partir do segundo."""

        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(429, json={"error": "rate"})
            return httpx.Response(200, json={"embedding": {"values": [0.2] * _DIMENSIONS}})

    async def sleep(delay: float) -> None:
        """Espera falsa: só anota o atraso pedido. A primeira espera do adaptador é 0,5 s."""
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
        """Conta os pedidos em voo e guarda o maior número visto ao mesmo tempo."""

        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            nonlocal in_flight, max_in_flight
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
            # Cede o loop com o pedido ainda em voo, para os outros pedidos do `gather`
            # entrarem. Só assim o semáforo de 4 vagas chega a limitar alguma coisa.
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
    """O adaptador real com o transporte falso, a chave `test-key` e 768 dimensões.

    Sem `sleep`, vale o `asyncio.sleep` padrão do adaptador.
    """
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
