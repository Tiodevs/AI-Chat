# Parte 13 · Testes

> **Você vai entender:** que suítes existem, o que cada uma prova, como os falsos substituem o Gemini e o LangSmith, como a integração usa um PostgreSQL de verdade sem tocar em banco remoto, e como escrever um teste novo.
>
> **Leia antes:** a [seção 21 da especificação](../sdd/entrega.md#21-testes) e o [ADR-004](../adr/004-gemini-atras-de-portas.md). **Tempo:** 45 minutos.

## 1. A pirâmide

```mermaid
flowchart TB
  subgraph topo["Lento e realista"]
    live["e2e ao vivo · 4 arquivos, 18 testes<br/>API real com o adaptador demo, vite preview, axe, CSP, teclado e desempenho"]
    mocked["e2e simulado · 6 arquivos, 12 testes<br/>Playwright com a API simulada por page.route"]
  end
  subgraph meio["Integração"]
    integ["API, integração · 18 arquivos, 113 casos<br/>PostgreSQL com pgvector de verdade"]
  end
  subgraph base["Rápido e isolado"]
    unit["API, unidade · 39 arquivos, 332 casos<br/>domínio, workflows com falsos, regras de HTTP"]
    vitest["Frontend, Vitest · 18 arquivos, 161 casos<br/>modelos, telas, leitor SSE, presets, tokens"]
    arch["Arquitetura · 24 casos<br/>e contrato · 3 casos"]
  end
  live --- mocked --- integ --- unit
  integ --- vitest
  unit --- arch
  evals["Avaliações no LangSmith<br/>o modelo real, fora da CI padrão"] -.- live
```

As contagens são dos casos executados em 2026-11-08, com os parametrizados contados um a um: 472 na API e 161 no Vitest (153 no projeto `dom` e 8 no `node`). Além deles, há 54 histórias no Storybook: a CI só as constrói, e o axe delas aparece no painel do Storybook, sem reprovar nada (parte 12).

| Suíte | Onde | Como rodar | Precisa |
|---|---|---|---|
| Unidade da API | [`apps/api/tests/unit`](../../apps/api/tests/unit/README.md) | `uv run pytest tests/unit` | Nada, menos o caso do aviso da seção 2 |
| Arquitetura | [`apps/api/tests/architecture`](../../apps/api/tests/architecture/README.md) | `uv run pytest tests/architecture` | Nada |
| Contrato | [`apps/api/tests/contract`](../../apps/api/tests/contract/README.md) | `uv run pytest tests/contract` | Nada: um transporte HTTP falso faz o papel do Gemini |
| Integração | [`apps/api/tests/integration`](../../apps/api/tests/integration/README.md) | `uv run pytest tests/integration` | `DATABASE_URL` num PostgreSQL com pgvector **local** |
| Vitest | Ao lado de cada arquivo, em `apps/web/src` ([lista](../../apps/web/src/test/README.md)) | `pnpm test` | Nada |
| e2e simulado | [`apps/web/e2e`](../../apps/web/e2e/README.md) | `pnpm exec playwright test` | O Chromium do Playwright |
| e2e ao vivo | [`apps/web/e2e/live`](../../apps/web/e2e/README.md) | `pnpm exec playwright test -c playwright.live.config.ts` | Um PostgreSQL vazio ou descartável |
| Avaliações | [`evals`](../../evals/README.md) | `uv run python -m app.scripts.run_evals` | Chaves do Gemini e do LangSmith |

O [README dos testes da API](../../apps/api/tests/README.md) e o [do Vitest](../../apps/web/src/test/README.md) listam cada arquivo e o que ele prova. A tabela "teste → requisito" é a [seção 21.1](../sdd/entrega.md#211-ci-padrão).

## 2. Os falsos

Nenhum teste automático chama o Gemini ou o LangSmith (NFR-3). Isso é possível porque o código depende das portas, e não dos provedores (parte 3):

| Falso | Substitui | Como é usado |
|---|---|---|
| [`FakeChatProvider`](../../apps/api/app/adapters/fake_chat.py) | O chat do Gemini | O teste programa a resposta: `FakeChatProvider(structured=QuestionClassification(...), tokens=["11:00 [1]."])`. Ele guarda cada chamada (`structured_calls`, `stream_calls`) para o teste conferir o que o workflow mandou. Também simula uso de tokens, pausas no meio do fluxo e falhas |
| [`DeterministicEmbeddingProvider`](../../apps/api/app/adapters/deterministic_embedding.py) | O embedding | Um vetor estável por texto, gerado por hash |
| [`NoopFeedbackSink`](../../apps/api/app/adapters/noop_feedback.py) | O envio de feedback ao LangSmith | Aceita a nota e não faz nada |
| [`DemoChatProvider`](../../apps/api/app/adapters/demo_chat.py) e [`LexicalEmbeddingProvider`](../../apps/api/app/adapters/lexical_embedding.py) | Os dois, na e2e ao vivo | Respondem por regras, para as jornadas passarem com a API real sem chave ([ADR-014](../adr/014-adaptador-demo.md)) |

O [`conftest.py`](../../apps/api/tests/conftest.py) da raiz dos testes desliga o rastreamento do LangSmith antes de qualquer teste e limpa o cache da configuração entre eles, para um teste não herdar o `Settings` de outro. Um teste de [`test_trace_policy.py`](../../apps/api/tests/unit/test_trace_policy.py) ainda confere que o `ci.yml` não lê nenhuma chave do LangSmith. Cada arquivo de teste também tem falsos locais, com `_` no começo do nome, como o `_AlignedEmbedding` da integração, que dá vetores próximos a textos que precisam se encontrar na busca.

> [!WARNING]
> Um teste de unidade toca o banco: [`test_observability.py`](../../apps/api/tests/unit/test_observability.py) sobe a aplicação com o `lifespan` e não limpa a `DATABASE_URL`. Rodando de dentro de `apps/api`, ele lê o `.env`, abre o pool desse banco, marca como `failed` as versões presas em `processing` e lê as métricas do banco. Se o seu `.env` aponta para o PostgreSQL de development da Railway, a suíte de unidade grava nele. Enquanto isso não muda, rode a unidade com `DATABASE_URL=` vazia ou com o banco do Docker. A seção 21.1 diz que nenhum teste toca um banco da Railway.

Um teste típico do pipeline, de [`test_qa.py`](../../apps/api/tests/unit/test_qa.py), monta o workflow com os falsos, roda uma pergunta e confere o desfecho e o que **não** foi chamado:

```python
def test_provider_failure_before_generation_is_error() -> None:
    chat, embeddings, search = _parts(ProviderUnavailable("indisponível"))
    result = _run(chat, embeddings, search, "Qual é o horário?")
    assert result.outcome is Outcome.ERROR
    assert result.text == UNAVAILABLE
    assert chat.stream_calls == []
```

## 3. A integração com um banco de verdade

A busca híbrida, os bloqueios, as restrições únicas e a retenção só se provam num PostgreSQL com pgvector. O [`conftest.py` da integração](../../apps/api/tests/integration/conftest.py):

1. Lê `DATABASE_URL` do ambiente, nunca do `.env`, e só aceita `localhost`, `127.0.0.1` ou `::1`. Uma URL remota faz a suíte pular, para nenhum teste tocar um banco da Railway: a integração é destrutiva, apaga a extensão `vector` em cascata e desfaz as migrações até a `0001` antes de refazê-las.
2. Sem banco local, pula. Com `REQUIRE_INTEGRATION_DB=1`, como no job `api` da CI, falha em vez de pular, para a CI nunca ficar verde com a integração inteira pulada (Etapa 11.1).
3. Roda as migrações do Alembic no começo da sessão de teste.
4. Não há rollback por teste: os dados de cada teste são únicos (`uuid4`), a limpeza fica num `finally`, e relógios fixos em anos distantes separam os números agregados. Por isso a suíte depende da ordem e não roda em paralelo.

Para rodar localmente, um banco descartável no Docker basta:

```bash
docker compose up -d db
```

```bash
REQUIRE_INTEGRATION_DB=1 DATABASE_URL=postgresql://atrium:atrium@127.0.0.1:5432/atrium uv run pytest tests/integration
```

## 4. Os dois e2e

| | Simulado | Ao vivo |
|---|---|---|
| Configuração | [`playwright.config.ts`](../../apps/web/playwright.config.ts) | [`playwright.live.config.ts`](../../apps/web/playwright.live.config.ts) |
| Frontend | `pnpm dev` | `vite preview`, com os cabeçalhos de produção |
| API | Simulada por `page.route`, com as respostas em `e2e/api.ts` e vizinhos | A de verdade, com o adaptador `demo`, depois de migrar, criar o admin e semear o corpus |
| Pega | Quebras de interface, depressa, em celular com movimento reduzido e uma vez com movimento | Jornadas inteiras, violações do axe e de CSP, uso só com teclado e as metas de desempenho da seção 5.3 |
| Na CI | Job `web` | Job `e2e` |

## 5. Escrever um teste novo

| Você mudou | Escreva | Onde |
|---|---|---|
| Uma regra do domínio | Um teste de unidade da função pura | `apps/api/tests/unit/test_<assunto>.py` |
| Um workflow | Um teste de unidade com o `FakeChatProvider` programado | `tests/unit/test_qa.py` ou `test_registration_workflow.py` |
| Uma consulta ou uma transação | Um teste de integração | `apps/api/tests/integration/` |
| Uma rota | Um teste de integração com o `TestClient` e o banco, ou de unidade com `dependency_overrides` | Um dos dois |
| Um modelo do frontend | Um `model.test.ts` ao lado | `apps/web/src/features/<feature>/` |
| Uma tela | Um teste com Testing Library, que use as consultas `findBy` para o que carrega sob demanda | O `*.test.tsx` da feature |
| Um componente de `ui` ou `patterns` | Uma história no Storybook com os estados da seção 14.7 | O `*.stories.tsx` ao lado |
| Um prompt | Uma `PROMPT_VERSION` nova e o hash novo em `test_prompt_versions.py`, mais o resultado das avaliações na PR | `apps/api/app/prompts/` |

Cada critério de aceite de uma etapa liga ao teste que o prova, na descrição da PR (DP-9).

## Para praticar

1. Rode a unidade da API e leia o resumo: `uv run pytest tests/unit -q`, em `apps/api`.
2. Escreva um teste de unidade para `reciprocal_rank_fusion` com uma lista vazia. O que a função devolve?
3. Em [`test_qa.py`](../../apps/api/tests/unit/test_qa.py), ache o teste que prova que `medical_advice` não chama a recuperação.
4. Rode só o leitor SSE do frontend: `pnpm exec vitest run src/lib/sse.test.ts`, em `apps/web`, e leia como ele junta eventos que chegam partidos.

**Próxima:** [Parte 14 · Entrega e operação](14-entrega-e-operacao.md)
