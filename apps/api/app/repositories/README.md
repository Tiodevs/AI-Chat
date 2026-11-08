# repositories

Consultas, inclusive busca vetorial e de texto completo, sem construção de prompt: a camada de repositório da [seção 6.2 do SDD](../../../../docs/sdd/arquitetura.md#62-mvc-com-as-camadas-de-que-um-sistema-de-ia-precisa). Cada repositório recebe a `AsyncSession` que o serviço abriu numa `UnitOfWork` e não faz commit; quem é dono da transação é o serviço ([seção 6.4](../../../../docs/sdd/arquitetura.md#64-transações-e-concorrência)).

## Arquivos

| Arquivo | O que faz | Quem usa |
|---|---|---|
| [`__init__.py`](__init__.py) | Docstring do pacote: o contrato de todos os repositórios | O pacote |
| [`audit.py`](audit.py) | `AuditRepository.record` grava um evento em `audit_events`, na transação da ação auditada | `DocumentAdminService`, `InsightsService`, `PrivacyQueueService` e `AccountService` |
| [`auth_sessions.py`](auth_sessions.py) | Cria, encontra (`get_active`), revoga e apaga sessões pelo SHA-256 do cookie | `AuthService`, `RegistrationService`, `ConversationService`, `AccountService` e `BootstrapAdminService` |
| [`bootstrap.py`](bootstrap.py) | O `pg_advisory_xact_lock` que serializa a criação do admin inicial | `BootstrapAdminService` |
| [`consents.py`](consents.py) | Histórico de consentimentos: aceite dos Termos vigentes, concessão, revogação e lista | `AuthService`, `RegistrationService` e `AccountService` |
| [`conversations.py`](conversations.py) | Chaves de convidado, conversas, mensagens com a alocação de `created_at`, feedback e o erro `DuplicateClientMessage` | `ConversationService`, `RegistrationService` e `AccountService` |
| [`documents.py`](documents.py) | SQL do corpus: versão nova, publicação, falha, trava do documento e lista do admin; também o `SeedLock` e `vector_literal` | `DocumentAdminService`, `IngestionService`, `SeedService` e `RetrievalRepository` |
| [`insights.py`](insights.py) | Agregados do painel, conversas que o inspetor pode abrir, mensagens com nota e a identidade para revelar | `InsightsService` |
| [`ops_metrics.py`](ops_metrics.py) | Pedidos de titular abertos e atrasados, total apagado por regra e a última execução da retenção | `refresh_database_metrics`, chamado pelo `GET /metrics` |
| [`privacy_requests.py`](privacy_requests.py) | Grava o pedido de titular, lê a fila numa consulta só e trava o pedido para mudar o status | `PrivacyRequestService` e `PrivacyQueueService` |
| [`rate_limits.py`](rate_limits.py) | `increment`: o upsert atômico que conta os pedidos de um balde na janela | `AuthService`, `RegistrationService`, `ConversationService`, `DocumentAdminService` e `PrivacyRequestService` |
| [`readiness.py`](readiness.py) | `SELECT 1`, a extensão `vector` e o tipo real de `chunks.embedding`, pelos catálogos | `ReadinessService`, chamado pelo `GET /ready` |
| [`registration.py`](registration.py) | Sessões de cadastro: criar, ler, travar com `FOR UPDATE` e gravar o registro inteiro | `RegistrationService` |
| [`retention.py`](retention.py) | Um DELETE por regra da seção 11.6 e a linha de `retention_runs` de cada execução | `RetentionService`, rodado pelo `retention-job` |
| [`retrieval.py`](retrieval.py) | As duas consultas da busca híbrida: vizinhos por cosseno e texto completo com o piso de similaridade | `RetrievalService` |
| [`token_usage.py`](token_usage.py) | Lê o contador diário de tokens e soma nele por upsert | `PostgresTokenBudget` |
| [`users.py`](users.py) | Contas: busca por e-mail e por id, `touch` do login, perfil, contagem por papel, criação e exclusão | `AuthService`, `RegistrationService`, `AccountService` e `BootstrapAdminService` |

## Como ler

1. Comece pelo contrato em `__init__.py` e veja quem abre e fecha a transação: [`app/db/session.py`](../db/session.py) e [`app/db/unit_of_work.py`](../db/unit_of_work.py).
2. Consultas do ORM, as mais simples: `users.py`, `auth_sessions.py`, `consents.py`, `audit.py` e `conversations.py`.
3. Concorrência: os upserts de `rate_limits.py` e `token_usage.py`, os `FOR UPDATE` de `registration.py`, `privacy_requests.py` e `DocumentRepository.lock`, e os advisory locks de `bootstrap.py` e do `SeedLock`.
4. SQL escrito à mão: `documents.py`, `retrieval.py` e `insights.py`.
5. Operação: `retention.py`, `ops_metrics.py` e `readiness.py`.

Os conceitos que ajudam:

- **`AsyncSession`.** `execute` roda o comando e devolve um `Result`; `scalar` devolve a primeira coluna da primeira linha, ou `None`; `scalars` percorre a primeira coluna; `get` busca pela chave primária e olha antes o mapa de identidade da sessão.
- **`flush()` não é commit.** Ele envia os INSERTs e UPDATEs pendentes dentro da transação aberta. Um erro do banco, como uma restrição única violada, aparece ali, e o serviço o transforma num erro de domínio.
- **`text("... :nome")`.** SQL escrito à mão com parâmetros nomeados. O valor viaja separado do texto do SQL, então não há injeção. Os pedaços de SQL montados com `+` são constantes do próprio arquivo.
- **`RETURNING`.** INSERT, UPDATE e DELETE devolvem as linhas afetadas. A retenção conta o que apagou assim, e `revoke` sabe se algo mudou.
- **`INSERT ... ON CONFLICT DO UPDATE`.** O upsert do PostgreSQL, atômico: cria a linha ou soma na que existe, com a linha travada.
- **`SELECT ... FOR UPDATE`.** Trava a linha lida até o fim da transação; outra transação que queira a mesma linha espera.
- **Advisory lock.** Um lock sobre um número escolhido pela aplicação. `pg_advisory_xact_lock` dura até o fim da transação; `pg_advisory_lock` dura até o `pg_advisory_unlock` ou até a conexão cair.
- **pgvector e texto completo.** `<=>` é a distância de cosseno, e a similaridade é `1 - distância`. `websearch_to_tsquery('portuguese', ...)` transforma texto livre numa consulta, `@@` casa a consulta com o `tsv`, e `ts_rank` ordena.
- **SQL do painel.** `JOIN LATERAL` roda uma subconsulta por linha de fora, `count(*) FILTER (WHERE ...)` conta só parte das linhas, e `array_agg(... ORDER BY ...)[1]` pega o primeiro de uma lista ordenada.

### A busca híbrida, passo a passo

O passo a passo da [seção 8.4](../../../../docs/sdd/arquitetura.md#84-recuperação-híbrida), com onde cada parte mora. O `QaWorkflow` chama `RetrievalService.search_by_vector` com a pergunta reescrita e o vetor dela.

| Passo | Onde | O que acontece |
|---|---|---|
| 1 | `RetrievalRepository.nearest` | Os 20 chunks pesquisáveis mais próximos pelo `<=>`, cada um com a similaridade |
| 2 | `RetrievalService.search_by_vector` | Descarta os que ficam abaixo de `RETRIEVAL_MIN_SIMILARITY` |
| 3 | `RetrievalRepository.keyword` | Até 20 chunks pesquisáveis que casam com `websearch_to_tsquery`, por `ts_rank`, já com o piso no SQL |
| 4 | `reciprocal_rank_fusion`, em [`app/domain/ranking.py`](../domain/ranking.py) | Funde as duas listas com a constante 60 |
| 5 | `RetrievalService.search_by_vector` | Devolve os 6 primeiros |

As duas consultas usam o predicado de chunk pesquisável da [seção 8.2](../../../../docs/sdd/arquitetura.md#82-índices-e-o-predicado-de-busca), a constante `_SEARCHABLE`, e o índice parcial de cada uma: HNSW para o `<=>` e GIN para o `@@`.

### Travas e atomicidade

| Mecanismo | Onde | Para quê |
|---|---|---|
| `SELECT ... FOR UPDATE` | `DocumentRepository.lock` | Substituir, tentar de novo e arquivar o mesmo documento, um de cada vez |
| `SELECT ... FOR UPDATE` | `RegistrationRepository.lock` | Dois turnos ou dois aceites da mesma sessão de cadastro em fila |
| `SELECT ... FOR UPDATE` | `PrivacyRequestRepository.lock` | Dois admins não fecham o mesmo pedido de titular |
| `pg_advisory_xact_lock` | `BootstrapRepository.lock` | Duas execuções do bootstrap criam um admin só |
| `pg_advisory_lock` de sessão | `SeedLock` | Uma semente por vez, através de várias transações |
| `ON CONFLICT DO UPDATE` | `RateLimitRepository.increment` e `TokenUsageRepository.add` | Contar sem perder incremento entre pedidos simultâneos |
| Restrição única e `IntegrityError` | `insert_message`, `insert_feedback` e `UserRepository.insert` | Mensagem repetida, segunda nota e e-mail já usado viram 409 no serviço |

## Testes

Testes de integração, que só rodam com `DATABASE_URL` em localhost (veja o [README da pasta](../../tests/integration/README.md)):

- [`test_retrieval.py`](../../tests/integration/test_retrieval.py): busca híbrida, piso de similaridade na lista por palavra, documento arquivado fora e no máximo 6 resultados.
- [`test_seed.py`](../../tests/integration/test_seed.py): semente idempotente, duas execuções simultâneas sob o `SeedLock`, versão com falha e versões presas.
- [`test_admin_documents.py`](../../tests/integration/test_admin_documents.py): upload, substituição, nova tentativa, arquivamento, auditoria e o limite de uploads.
- [`test_conversations.py`](../../tests/integration/test_conversations.py): mensagens, `client_message_id` repetido, feedback, convidados e limites de perguntas.
- [`test_registration.py`](../../tests/integration/test_registration.py), [`test_auth.py`](../../tests/integration/test_auth.py), [`test_bootstrap_admin.py`](../../tests/integration/test_bootstrap_admin.py) e [`test_account.py`](../../tests/integration/test_account.py): contas, sessões, consentimentos, o lock do admin e a exclusão em cascata.
- [`test_privacy_requests.py`](../../tests/integration/test_privacy_requests.py) e [`test_admin_privacy.py`](../../tests/integration/test_admin_privacy.py): canal do titular e fila do admin.
- [`test_admin_insights.py`](../../tests/integration/test_admin_insights.py): visão geral, qualidade, inspetor e revelação.
- [`test_retention.py`](../../tests/integration/test_retention.py), [`test_ops_metrics.py`](../../tests/integration/test_ops_metrics.py), [`test_token_budget.py`](../../tests/integration/test_token_budget.py) e [`test_database.py`](../../tests/integration/test_database.py): retenção, métricas do banco, orçamento e `/ready`.

O [teste de arquitetura](../../tests/architecture/test_layers.py) confere que nenhum repositório importa LangChain, LangGraph, LangSmith ou FastAPI. Em `apps/api`:

```bash
uv run pytest tests/integration tests/architecture
```

## Leia também

- [SDD 6.2](../../../../docs/sdd/arquitetura.md#62-mvc-com-as-camadas-de-que-um-sistema-de-ia-precisa) e [6.4](../../../../docs/sdd/arquitetura.md#64-transações-e-concorrência): camadas, transações curtas e locks.
- [SDD 8.2](../../../../docs/sdd/arquitetura.md#82-índices-e-o-predicado-de-busca) e [8.4](../../../../docs/sdd/arquitetura.md#84-recuperação-híbrida): índices, predicado de busca e recuperação híbrida.
- [SDD 10.4](../../../../docs/sdd/seguranca.md#104-limites-de-taxa), [11.6](../../../../docs/sdd/lgpd.md#116-retenção-e-eliminação) e [18.3](../../../../docs/sdd/observabilidade.md#183-métricas-painéis-e-alertas): limites de taxa, retenção e métricas do banco.
- [README dos modelos](../models/README.md), com o diagrama das tabelas.
- [Guia, parte 3: a API por dentro](../../../../docs/guia/03-api-por-dentro.md), [parte 5: RAG, corpus e ingestão](../../../../docs/guia/05-rag-corpus-e-ingestao.md) e [parte 9: dados e migrações](../../../../docs/guia/09-dados-e-migracoes.md).
