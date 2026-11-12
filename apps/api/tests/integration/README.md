# integration

Testes de integração da API contra PostgreSQL com pgvector: as rotas pelo `TestClient`, os serviços e os repositórios com o banco de verdade, e os provedores de IA falsos. É a suíte que prova NFR-5 e a maior parte da tabela da [seção 21.1 do SDD](../../../../docs/sdd/entrega.md#211-ci-padrão).

## Arquivos

São 113 testes em 18 arquivos. "O que cobre" diz o que cada arquivo exercita, os requisitos e as seções do SDD.

| Arquivo | O que prova | O que cobre |
|---|---|---|
| [`__init__.py`](__init__.py) | Vazio. Faz da pasta o pacote `tests.integration`: um teste importa helpers de outro, e `unit/` também tem um `test_registration.py`. | Coleta do pytest |
| [`conftest.py`](conftest.py) | Fixtures `database_url` e `migrated_database`: só banco local, migrado uma vez por sessão. Sem banco, pula; com `REQUIRE_INTEGRATION_DB=1`, falha. | NFR-5, seção 21.1 |
| [`test_account.py`](test_account.py) | 9 testes. Correção do perfil, campos sensíveis só com a personalização, histórico de consentimentos, exportação só do titular, exclusão com auditoria só do id, admin que não se exclui, novo aceite dos Termos e rotas que exigem sessão e `Origin`. | `/v1/me`, `/v1/me/export`, `/v1/me/consents` e `/v1/conversations`. FR-9, NFR-12, seções 11.5, 11.6 e 12 |
| [`test_admin_documents.py`](test_admin_documents.py) | 8 testes. Upload recusado por tamanho ou tipo, ingestão até `ready` com auditoria, versão anterior respondendo durante a troca, falha com nova tentativa, arquivo, 409 com versão em `processing`, limite de 30 uploads por hora e 403 ou 401 fora do admin. | `/v1/admin/documents`, `DocumentAdminService` e `IngestionService`. FR-10 a FR-12, NFR-10, seções 7.3, 8.1, 10.4 e 12 |
| [`test_admin_insights.py`](test_admin_insights.py) | 6 testes. Indicadores contra o período anterior, inspetor só com convidados e membros que consentiram, `conversation.view`, conversa oculta sem auditoria, revelação só com motivo e 403 para membro. | `/v1/admin/overview`, `/v1/admin/quality` e `/v1/admin/conversations`. FR-15, NFR-10, seções 11.8, 12 e 15.5 |
| [`test_admin_privacy.py`](test_admin_privacy.py) | 6 testes. Atrasados primeiro, `dsr.update` sem nota nem e-mail, fechamento só com nota, pedido fechado que não muda, validação, `bad_origin` e 403 ou 401 fora do admin. | `/v1/admin/privacy/requests`. FR-16, NFR-10, NFR-12, seções 11.5 e 12 |
| [`test_auth.py`](test_auth.py) | 7 testes. Mesma mensagem para e-mail conhecido ou não, cookie só do host com hashes no banco, logout que revoga, limites por e-mail e por IP, membro barrado no admin e cookie `Secure` em production. Também guarda os helpers de login e de usuário que outros arquivos importam. | `/v1/auth/*`, `/v1/me` e `/v1/admin/probe`. FR-7, NFR-7, NFR-10, NFR-11, seções 10.3, 10.4 e 12 |
| [`test_bootstrap_admin.py`](test_bootstrap_admin.py) | 2 testes. O admin inicial nasce uma vez, o último não sai e duas execuções simultâneas criam um só. | `BootstrapAdminService`, o mesmo do script do pré-deploy. Seções 6.4 e 10.5 |
| [`test_conversations.py`](test_conversations.py) | 17 testes. Resposta citada pelo SSE, 409 do reenvio, desconexão que grava `cancelled` e o uso parcial, pergunta médica gravada como marcador, telefone fora do contexto com `replace`, histórico lido do banco, feedback, dono da conversa, cookie de convidado, limites, diagnóstico e orçamento estourado. Também guarda os helpers de conversa que outros arquivos importam. | `/v1/conversations`, `/v1/messages/{id}/feedback` e `/v1/diagnostics/stream`. FR-1 a FR-4, FR-9, FR-14, FR-17, FR-18, NFR-6, NFR-11, NFR-13, seções 6.4, 7.1, 10.3, 10.4 e 12 |
| [`test_corpus_schema.py`](test_corpus_schema.py) | 2 testes. `vector(768)`, `tsv` gerado em português, índices da seção 8.2 e restrições das tabelas do corpus. | Migração `0002_corpus`. Seções 8.1 e 8.2 |
| [`test_database.py`](test_database.py) | 10 testes. A regra de banco do `conftest.py`, colunas e restrições iguais aos modelos e `/ready` sem a extensão ou com a dimensão divergente. | Migrações até `0009_message_request_id` e `/ready`. NFR-5, NFR-9, seções 8.1 e 21.1 |
| [`test_missing_gemini_key.py`](test_missing_gemini_key.py) | 3 testes. Sem `GEMINI_API_KEY`, os provedores falham só no uso, o diagnóstico responde e a pergunta recebe a indisponibilidade. | Fábricas de provedor e `/v1/diagnostics/stream`. Seções 7.1, 10.1, 17 e 22.1 |
| [`test_ops_metrics.py`](test_ops_metrics.py) | 1 teste. Pedidos abertos, atrasados e a última execução da retenção lidos do banco. | `refresh_database_metrics`. Seção 18.3 |
| [`test_privacy_requests.py`](test_privacy_requests.py) | 7 testes. Prazo de 15 dias, sexto pedido do IP no dia com 429, validação do contato e da descrição, pedido de membro que sobrevive à exclusão da conta e `Origin` obrigatório. | `POST /v1/privacy/requests`. FR-16, NFR-12, seções 8.1, 10.4, 11.5 e 12 |
| [`test_process_lifetime.py`](test_process_lifetime.py) | 3 testes. Cinco falhas em pedidos diferentes abrem o circuito, o `AiRuntime` nasce uma vez por app e os pedidos reaproveitam o pool do `lifespan`. | `AiRuntime`, `GeminiChatProvider` e `app/db/session.py`. Seções 6.4 e 7.1, Etapa 12.4 |
| [`test_registration.py`](test_registration.py) | 10 testes. Orçamento estourado sem chamar o modelo, tokens de cada turno, senha fora da transcrição e do log, aceites obrigatórios, campos sensíveis descartados, chat e formulário com os mesmos consentimentos, aceite repetido, conversa de convidado anexada, e-mail repetido e limite por IP. | `/v1/registration` e `RegistrationService`. FR-5 a FR-9, NFR-13, seções 7.2, 8.1, 8.5 e 10.4 |
| [`test_retention.py`](test_retention.py) | 11 testes. Cada regra apaga só o que passou do prazo, e `run_all` roda todas. | `RetentionService` e `RetentionRepository`. Seção 11.6 |
| [`test_retrieval.py`](test_retrieval.py) | 4 testes. A pergunta de visita acha o chunk de visita, o piso corta quem só casa por palavra, o documento arquivado some e saem no máximo 6 chunks. | `IngestionService`, `RetrievalService` e o pgvector. FR-2, FR-12, seções 8.2 a 8.4 |
| [`test_seed.py`](test_seed.py) | 6 testes. Semente idempotente e sem duplicar em corrida, versão com falha que mantém a anterior, prefixos de embedding, documento vazio e versões presas marcadas na subida. | `SeedService`, `IngestionService` e o `lifespan`. FR-11, FR-13, seções 6.4, 7.3 e 8.3 |
| [`test_token_budget.py`](test_token_budget.py) | 1 teste. O contador soma o dia UTC, e o teto estoura quando o uso o iguala. | `TokenUsageRepository` e `PostgresTokenBudget`. NFR-13, seções 7.1 e 8.1 |
| [`test_handoff.py`](test_handoff.py) | 18 testes. Migração `0010`, script do papel, papéis separados, sessão de 12 horas, aceite, regra da oferta, disponibilidade, 409 da pergunta durante o atendimento sem chamar o modelo, marcadores da remoção, um ativo por visitante, encerramento pelo visitante, limite de pedidos, corrida de dois atendentes, fila sem conteúdo, 404 para outro atendente, remoção com auditoria, encerramento com motivo, leitura de encerrado com motivo e a varredura. | `/v1/handoff`, `/v1/conversations/{id}/handoff`, `/v1/attendance` e `/v1/admin/handoffs`. FR-19, FR-21, FR-22, FR-24 a FR-26, NFR-18, NFR-20, seção 29 |
| [`test_realtime.py`](test_realtime.py) | 7 testes. `NOTIFY` só depois do commit e com carga de ids, ouvinte que reconecta, retomada pelo `Last-Event-ID`, `reconnect` no fim do fluxo, sessão revogada que fecha o fluxo, aviso perdido entregue pelo tique e console de outro atendente sem as mensagens. | `adapters/realtime.py`, `services/handoff.py`, `services/attendance.py`. FR-23, NFR-18, NFR-19, seção 29.6, ADR-016 |

## Como ler

1. `conftest.py`: como a suíte escolhe e migra o banco.
2. `test_auth.py`: o molde das fixtures `api`. Cada uma grava as variáveis com `monkeypatch.setenv`, limpa o cache de `get_settings`, chama `create_app()` e troca dependências em `dependency_overrides`, a começar pelo `get_clock`.
3. `test_conversations.py`: o fluxo SSE com os falsos injetados no `get_qa_workflow` e a desconexão por ASGI cru.
4. `test_retrieval.py` e `test_seed.py`: o pgvector de verdade, com vetores escolhidos à mão.
5. `test_registration.py`: o `FakeChatProvider` roteirizado turno a turno.
6. O resto por assunto: conta, canal do titular, admin, retenção, métricas, orçamento, admin inicial, chave ausente e vida de processo. Por fim, `test_database.py` e `test_corpus_schema.py`, que conferem o esquema.

Conceitos que ajudam:

- **Banco dividido, limpeza manual.** Nenhum teste é desfeito por rollback. Cada um cria linhas com e-mails, ids e IPs únicos (`uuid4().hex`) e apaga o que criou num `finally`. Relógios parados em datas distantes, como 1999, 2031 e 2032, separam os agregados dos dados de outros testes.
- **Uma conexão por uso.** Os helpers abrem `open_session` com `UnitOfWork`, uma transação curta cada, dentro de um `asyncio.run`. Sem o `lifespan` não há pool, então cada uso abre uma conexão (seção 6.4). `with TestClient(app)` roda o `lifespan`: é assim que `test_seed.py` vê a subida marcar versões presas e `test_process_lifetime.py` conta os checkouts do pool.
- **Tarefas de fundo.** O `TestClient` termina as tarefas de fundo antes de devolver a resposta, então a ingestão do admin e o envio do feedback já aconteceram quando o teste confere.
- **Falsos.** O `FakeChatProvider` (`app/adapters/fake_chat.py`) devolve o que o teste roteiriza: saída estruturada, chamada de ferramenta e tokens, com uso de tokens, gancho no início do fluxo e pausa depois de N tokens. O `DeterministicEmbeddingProvider` (`app/adapters/deterministic_embedding.py`) gera um vetor unitário por hash. Ele não aproxima textos de mesmo sentido, então `test_retrieval.py`, `test_seed.py` e `test_admin_documents.py` escolhem os vetores com falsos próprios. O `NoopFeedbackSink` vem do `get_feedback_sink`, porque o `conftest.py` da raiz desliga o `LANGSMITH_TRACING`; `test_conversations.py` troca o sink por um que guarda as notas. `test_process_lifetime.py` usa o `GeminiChatProvider` de verdade sobre um backend falso, sem rede.
- **Limites de taxa.** Um limite estourado é preparado gravando a janela já cheia em `rate_limit_windows`, com o mesmo `bucket_key` e o mesmo `fixed_window_start` da API. Com o relógio às 12:07, sobram 3180 s na janela de uma hora e 480 s na de 15 minutos.
- **Advisory locks.** A semente segura um `pg_advisory_lock` de sessão, e o admin inicial um `pg_advisory_xact_lock` de transação. Os testes de corrida rodam duas chamadas com `asyncio.gather`.

## Testes

Precisam de um PostgreSQL local com a extensão `vector`, de preferência vazio e só para os testes. O `db` do `docker-compose.yml` da raiz usa a mesma imagem e as mesmas credenciais da CI, mas os testes apagam dados dele. Em `apps/api`:

```bash
DATABASE_URL=postgresql://atrium:atrium@127.0.0.1:5432/atrium uv run pytest tests/integration
```

- **Só localhost.** O `conftest.py` aceita só `localhost`, `127.0.0.1` ou `::1`. Uma URL remota, como a da Railway, é ignorada (seção 21.1). Sem banco local, 105 testes pulam e só rodam os 8 que não usam `migrated_database`.
- **`REQUIRE_INTEGRATION_DB=1`.** O job `api` do `ci.yml` define essa variável, que troca o pulo por falha: sem o contêiner `pgvector/pgvector:pg18`, a CI fica vermelha em vez de passar com a integração pulada (NFR-5). Para ver a falha: `REQUIRE_INTEGRATION_DB=1 DATABASE_URL= uv run pytest tests/integration -x`.
- **Marcador.** Todo arquivo marca os testes com `integration`, então `uv run pytest -m "not integration"` deixa a pasta de fora.
- **Efeitos destrutivos.** Use um banco descartável:
  - `test_database.py` remove a extensão `vector` com `CASCADE` e, para recriá-la, volta o Alembic a `0001_initial` e sobe a `head`. As tabelas das migrações 0002 a 0009 (corpus, conversas, cadastro, consentimentos, pedidos, retenção e tokens) voltam vazias.
  - `test_retrieval.py` apaga o documento `02-visiting` do corpus semeado.
  - `test_ops_metrics.py` apaga todos os pedidos de titular e todas as execuções da retenção.
  - `test_retention.py` aplica as regras da seção 11.6 ao banco inteiro.
  - `test_bootstrap_admin.py` rebaixa os admins existentes e os devolve no fim. Um teste interrompido no meio os deixa como `member`.
- **O que fica.** Algumas linhas sobram, sempre com sufixo único ou em datas de teste: os admins de `_insert_admin` em `test_retrieval.py` e `test_seed.py`, as linhas válidas de `test_database.py` e `test_corpus_schema.py`, as janelas de limite, as execuções em `retention_runs`, os pedidos de `test_ops_metrics.py`, o uso de tokens do dia parado de `test_conversations.py` e a chave de convidado do teste de anexação de `test_registration.py`.

## Leia também

- [SDD 21.1, CI padrão](../../../../docs/sdd/entrega.md#211-ci-padrão): o que cada teste prova e a regra do pulo.
- [SDD 22.3, GitHub Actions](../../../../docs/sdd/entrega.md#223-github-actions): o job `api`, que roda esta pasta.
- [SDD 6.4, transações e concorrência](../../../../docs/sdd/arquitetura.md#64-transações-e-concorrência)
- [SDD 8, desenho dos dados](../../../../docs/sdd/arquitetura.md#8-desenho-dos-dados)
- [README das suítes](../README.md)
- [Guia, parte 13: testes](../../../../docs/guia/13-testes.md) e [parte 9: dados e migrações](../../../../docs/guia/09-dados-e-migracoes.md)
