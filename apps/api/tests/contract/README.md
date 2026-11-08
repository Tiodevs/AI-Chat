# contract

Teste de contrato do adaptador de embedding do Gemini: um texto por pedido HTTP, vetores de 768 dimensões, nova tentativa em 429 e no máximo 4 pedidos simultâneos ([seção 17 do SDD](../../../../docs/sdd/observabilidade.md#17-portas-dos-provedores)). Roda na suíte padrão, com HTTP simulado, sem rede e sem banco.

## Arquivos

| Arquivo | O que prova | O que cobre |
|---|---|---|
| [`test_gemini_embedding.py`](test_gemini_embedding.py) | 3 testes. Cinco textos viram cinco pedidos `:embedContent`, cada um com um texto, `outputDimensionality` 768 e a chave no cabeçalho `x-goog-api-key`, e voltam cinco vetores. Um 429 é repetido depois de 0,5 s. Oito textos nunca passam de 4 pedidos em voo | `GeminiEmbeddingProvider` em `app/adapters/gemini_embedding.py`, seções 6.4, 17 e 25 |

A pasta não tem `__init__.py`. O pytest a encontra pelo `testpaths = ["tests"]` do `pyproject.toml`.

## Como ler

Um teste de contrato fixa a forma da conversa com um serviço externo sem chamá-lo. Aqui, cada teste injeta um `httpx.AsyncClient` com um transporte falso, uma classe `Transport` que recebe o pedido e devolve a resposta que o teste quer. O adaptador é o de produção. Só a rede é trocada.

O contrato existe por causa de um risco da [seção 25](../../../../docs/sdd/entrega.md#25-riscos): o `gemini-embedding-2` agrega num único vetor várias entradas enviadas juntas. Se alguém trocasse o laço por um pedido em lote, a busca passaria a comparar a pergunta com vetores misturados, e nenhum teste de unidade com o `DeterministicEmbeddingProvider` perceberia.

O que o adaptador ainda não faz, e por isso não está provado aqui: transformar `httpx.TimeoutException` e `ConnectError` no erro da porta, repetir em 503 e reaproveitar o cliente HTTP. A [Etapa 13.2](../../../../docs/plano-de-acao.md#etapa-132--embedding-resiliente-atrás-da-porta) corrige isso.

## Testes

Em `apps/api`:

```bash
uv run pytest tests/contract
```

O job `api` do `ci.yml` roda esta pasta junto com as outras suítes no `uv run pytest`. Nenhuma chave do Gemini é lida (NFR-3).

## Leia também

- [SDD 17](../../../../docs/sdd/observabilidade.md#17-portas-dos-provedores): as portas, os adaptadores e o contrato de embedding.
- [SDD 8.3](../../../../docs/sdd/arquitetura.md#83-texto-de-embedding): o texto enviado e a dimensão da coluna.
- [SDD 21.1](../../../../docs/sdd/entrega.md#211-ci-padrão): "O adaptador de embedding envia um pedido por texto".
- [ADR-004](../../../../docs/adr/004-gemini-atras-de-portas.md): Gemini atrás de portas, com falsos nos testes.
- [README das suítes](../README.md).
- [Guia, parte 5](../../../../docs/guia/05-rag-corpus-e-ingestao.md) e [parte 13](../../../../docs/guia/13-testes.md).
