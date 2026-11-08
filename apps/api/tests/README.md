# tests

Testes da API com Pytest, em quatro suítes. A execução padrão não chama o Gemini nem o LangSmith (NFR-3), e a integração roda contra PostgreSQL com pgvector de verdade no job `api` da CI (NFR-5). [Seção 21.1 do SDD](../../../docs/sdd/entrega.md#211-ci-padrão).

## Arquivos

| Arquivo | O que faz | Quem usa |
|---|---|---|
| [`__init__.py`](__init__.py) | Vazio. Faz de `tests` um pacote: os testes importam `tests.architecture.layers` e helpers de outros arquivos, e `test_registration.py` existe em `unit` e em `integration` sem colidir | O pytest |
| [`conftest.py`](conftest.py) | Desliga `LANGSMITH_TRACING` na importação e, antes e depois de cada teste, limpa o cache de `get_settings` e os clientes do LangSmith | As quatro suítes |
| [`unit/`](unit/README.md) | Domínio puro, configuração e HTTP, IA, observabilidade e arquivos do repositório | Job `api` |
| [`integration/`](integration/README.md) | Rotas, serviços, repositórios e migrações contra PostgreSQL com pgvector | Job `api` |
| [`architecture/`](architecture/README.md) | Direção de dependência entre as camadas, lida com `ast` | Job `api` |
| [`contract/`](contract/README.md) | O adaptador de embedding do Gemini com HTTP simulado | Job `api` |

## As quatro suítes

| Suíte | Arquivos | Testes coletados | O que prova | Banco | Rede |
|---|---|---|---|---|---|
| `unit` | 39 | 332 (253 funções, com os casos de `parametrize`) | As regras do domínio, a configuração, as guardas HTTP, o pipeline de perguntas e o cadastro com falsos, logs, spans, métricas, políticas de rastro, e arquivos do repositório como o catálogo do corpus, os prompts, os painéis e o `ci.yml` | Não, com uma exceção abaixo | Não |
| `integration` | 18 e o `conftest.py` | 113 | Os fluxos HTTP de ponta a ponta na API, a busca híbrida, a semente, a ingestão, a retenção, a auditoria, os limites de taxa e as migrações | Sim, local | Não |
| `architecture` | 1 e o helper `layers.py` | 24 | NFR-1, seção 6.2 | Não | Não |
| `contract` | 1 | 3 | Um texto por pedido de embedding, seção 17 | Não | Não, HTTP simulado |

São 472 testes coletados ao todo. A tabela da seção 21.1 diz o que cada caso prova, e o README de cada pasta diz em que arquivo ele está.

## Os falsos

Os três falsos da seção 17 ficam em `app/adapters`, ao lado dos adaptadores de verdade, porque implementam as mesmas portas (ADR-004).

| Falso | Porta | Arquivo | O que faz |
|---|---|---|---|
| `FakeChatProvider` | `ChatProvider` | `app/adapters/fake_chat.py` | Devolve o que o teste escreve: a saída estruturada, o resultado da ferramenta e os tokens do fluxo, ou uma exceção. Guarda as chamadas em `structured_calls`, `stream_calls` e `tool_calls`, conta tokens como o adaptador do Gemini e pode pausar o fluxo no meio (`pause_after`) para provar o cancelamento |
| `DeterministicEmbeddingProvider` | `EmbeddingProvider` | `app/adapters/deterministic_embedding.py` | Vetor unitário de 768 dimensões gerado por hash do texto. O mesmo texto dá sempre o mesmo vetor, mas textos parecidos não ficam perto: um teste que precisa de proximidade escreve o próprio embedding falso |
| `NoopFeedbackSink` | `FeedbackSink` | `app/adapters/noop_feedback.py` | Descarta o feedback. É o que `feedback_sink_for` devolve com o rastreamento desligado, como o `conftest.py` deixa |

Cada arquivo de teste também tem falsos locais, com `_` no nome, como relógios, orçamentos e repositórios em memória. Os testes de integração injetam os falsos com `dependency_overrides`, para uma variável esquecida não chamar o Gemini (seção 17). O `DemoChatProvider` e o `LexicalEmbeddingProvider`, do adaptador `demo`, não são falsos de teste: servem à e2e ao vivo do frontend (ADR-014) e são testados em `unit/test_demo_adapter.py`.

## Como ler

1. Este README e o [`conftest.py`](conftest.py).
2. [`architecture/`](architecture/README.md) e [`contract/`](contract/README.md), curtos e sem banco.
3. [`unit/`](unit/README.md), pela ordem sugerida no README dela.
4. [`integration/`](integration/README.md), começando pelo `conftest.py` da pasta.

Conceitos que ajudam:

- **Falso no lugar da porta.** Os workflows recebem as portas pelo construtor (seção 6.2), então um teste troca o Gemini por um falso sem tocar no código de produção.
- **Sem `pytest-asyncio`.** As corrotinas rodam com `asyncio.run` dentro do teste, ou por baixo do `TestClient`.
- **`TestClient` com ou sem `with`.** Sem `with`, o `lifespan` não roda e não abre o pool do banco. Com `with`, roda.
- **Cache da configuração.** Quem muda o ambiente com `monkeypatch` chama `get_settings.cache_clear()`; o `conftest.py` raiz também limpa antes e depois de cada teste.

## Testes

Em `apps/api`:

```bash
uv run pytest                        # as quatro suítes; sem banco local, a integração pula
uv run pytest tests/unit             # unidade
uv run pytest tests/architecture tests/contract
DATABASE_URL=postgresql://atrium:atrium@127.0.0.1:5432/atrium_test uv run pytest tests/integration
REQUIRE_INTEGRATION_DB=1 DATABASE_URL= uv run pytest tests/integration -x   # sem banco, falha
```

**Banco.** Só a integração precisa de banco. A fixture `database_url` lê `DATABASE_URL` do ambiente do processo, não do `apps/api/.env`, e aceita só `localhost`, `127.0.0.1` e `::1`. Sem banco local, ou com uma URL remota como a da Railway, a integração pula. O `migrated_database` roda as migrações do Alembic uma vez por sessão.

**Banco descartável.** A integração não desfaz nada no fim de cada teste e altera o banco inteiro: remove a extensão `vector` em cascata e refaz as migrações, apaga todos os pedidos de titular e as execuções de retenção e aplica as regras de retenção a todas as linhas. Use um banco criado só para isso, nunca o do `docker compose` com dados que você quer manter nem um banco da Railway. Os detalhes estão no [README da integração](integration/README.md).

**`REQUIRE_INTEGRATION_DB`.** Com o valor `1`, a falta de banco local vira falha em vez de pulo. O job `api` do `ci.yml` define a variável, para a CI não ficar verde com a integração inteira pulada (seção 21.1, Etapa 11.1). Na máquina, sem a variável, a integração continua pulando.

**A exceção da unidade.** `unit/test_observability.py` sobe o app com `with TestClient(...)`: o `lifespan` abre o pool da `DATABASE_URL` do ambiente ou do `apps/api/.env` e marca como `failed` as versões presas, e o `/metrics` lê o banco. Com a configuração local da seção 19, que aponta para o banco de development da Railway, esse teste conecta e escreve nele. Para a unidade não tocar banco nenhum, rode com `DATABASE_URL=` vazia.

**Na CI.** O job `api` do [`ci.yml`](../../../.github/workflows/ci.yml) roda `uv run ruff check`, `uv run mypy` e `uv run pytest`, com o contêiner `pgvector/pgvector:pg18` em `127.0.0.1:5432` e `REQUIRE_INTEGRATION_DB=1`. Um teste de unidade lê o próprio `ci.yml` para conferir que ele não cita o LangSmith. O frontend tem os próprios testes, em [`apps/web/src/test`](../../web/src/test/README.md) e [`apps/web/e2e`](../../web/e2e/README.md).

## Leia também

- [SDD 21.1](../../../docs/sdd/entrega.md#211-ci-padrão): o que a CI padrão prova, caso a caso.
- [SDD 17](../../../docs/sdd/observabilidade.md#17-portas-dos-provedores): as portas e os falsos.
- [SDD 6.2](../../../docs/sdd/arquitetura.md#62-mvc-com-as-camadas-de-que-um-sistema-de-ia-precisa) e [6.4](../../../docs/sdd/arquitetura.md#64-transações-e-concorrência): camadas, transações e o pool do `lifespan`.
- [SDD 19](../../../docs/sdd/entrega.md#19-ambientes-e-configuração): o banco de cada ambiente.
- [ADR-004](../../../docs/adr/004-gemini-atras-de-portas.md): Gemini atrás de portas, com falsos nos testes.
- [Guia, parte 13](../../../docs/guia/13-testes.md).
