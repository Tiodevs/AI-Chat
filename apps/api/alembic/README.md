# alembic

As migrações do banco, com o Alembic: cada revisão cria ou muda tabelas, índices e restrições do PostgreSQL. O banco real nasce daqui, e as entidades de [`app/models`](../app/models/README.md) descrevem o mesmo esquema. O desenho dos dados está na [seção 8 do SDD](../../../docs/sdd/arquitetura.md#8-desenho-dos-dados), e a regra de publicação, expand and contract, na [seção 22.1](../../../docs/sdd/entrega.md#221-railway).

## Arquivos

| Arquivo | O que faz | Quem usa |
|---|---|---|
| [`env.py`](env.py) | Roteiro que o Alembic executa nos comandos com banco: acha a URL, liga o logging e roda as revisões pela ponte síncrona do engine assíncrono. | O comando `alembic`, o pré-deploy da Railway e `tests/integration/conftest.py` |
| [`script.py.mako`](script.py.mako) | Modelo do arquivo de uma revisão nova (`alembic revision`). | Quem cria uma migração |
| [`versions/`](versions/) | As revisões, uma por arquivo, na ordem da tabela abaixo. | `env.py` |
| [`README.md`](README.md) | Este mapa. | Quem estuda a pasta |

A configuração fica fora da pasta, em [`../alembic.ini`](../alembic.ini), comentada linha a linha.

## Migrações

Cada revisão aponta para a anterior em `down_revision`, e o id é legível, no lugar do hash aleatório do Alembic. O nome do arquivo repete o id.

| Revisão | O que cria ou muda | Downgrade |
|---|---|---|
| [`0001_initial`](versions/0001_initial.py) | Extensão `vector` e as tabelas `users`, `auth_sessions`, `rate_limit_windows` e `audit_events`. | Apaga as quatro tabelas e a extensão. |
| [`0002_corpus`](versions/0002_corpus.py) | `documents`, `document_versions` e `chunks`, com o `embedding vector(768)`, o `tsv` gerado e os índices HNSW e GIN parciais em `active`. | Apaga as três tabelas e o corpus. |
| [`0003_token_usage`](versions/0003_token_usage.py) | `token_usage_days`, o contador do orçamento diário de tokens. | Apaga a tabela. |
| [`0004_conversations`](versions/0004_conversations.py) | `guest_keys`, `conversations`, `messages` (única em `conversation_id` e `client_message_id`) e `feedback`. | Apaga as quatro tabelas e as conversas. |
| [`0005_registration`](versions/0005_registration.py) | Restrição `users_visit_reason`, `consent_records` e `registration_sessions`. | Apaga as duas tabelas e a restrição. |
| [`0006_audit_survives_account`](versions/0006_audit_survives_account.py) | Tira a chave de `audit_events.actor_user_id` para `users`, para `account.delete` sobreviver à conta. | Apaga os eventos sem autor e devolve a chave. Perde auditoria. |
| [`0007_data_subject_requests`](versions/0007_data_subject_requests.py) | `data_subject_requests`, com `user_id` que vira nulo na exclusão da conta e índice em `due_at`. | Apaga a tabela e os pedidos. |
| [`0008_retention_runs`](versions/0008_retention_runs.py) | `retention_runs`, as execuções do `retention-job` que o `/metrics` lê, com índice em `ran_at`. | Apaga a tabela. |
| [`0009_message_request_id`](versions/0009_message_request_id.py) | Coluna anulável `messages.request_id`, para o inspetor de qualidade. | Apaga a coluna. |
| [`0011_whatsapp`](versions/0011_whatsapp.py) | Canal WhatsApp: `whatsapp_contacts`, `whatsapp_inbound_events`, `whatsapp_outbound_messages` e `whatsapp_handoff_relay`, e a coluna `channel` em `conversations` e `handoffs`. | Apaga as tabelas e as colunas de canal. |
| [`0010_handoffs`](versions/0010_handoffs.py) | Atendimento humano: `handoffs`, `attendant_presence` e `attendant_acknowledgements`, o papel `attendant` em `users` e as colunas `handoff_id`, `seq`, `author_user_id`, `redaction` e `redacted_at` em `messages`. | Apaga as tabelas e as colunas e volta as restrições de papel. |

A docstring de cada revisão explica o porquê de cada tabela, restrição e índice.

## Comandos

Rode em `apps/api`. A URL vem do `DATABASE_URL` do ambiente ou do `.env`.

```bash
uv run alembic upgrade head            # aplica as revisões pendentes
uv run alembic current                 # mostra a revisão em que o banco está
uv run alembic history                 # lista as revisões, da mais nova para a mais antiga
uv run alembic downgrade -1            # volta uma revisão
uv run alembic downgrade 0001_initial  # volta até a primeira revisão
uv run alembic upgrade head --sql      # só escreve o SQL, sem conectar
```

- `downgrade base` desfaz também a `0001_initial` e apaga a extensão `vector`. Nenhum teste passa por esse caminho.
- Com o PostgreSQL, o DDL é transacional: as revisões de um `upgrade` rodam numa transação só, e uma falha no meio desfaz todas.
- O `alembic.ini` deixa só os avisos no log, então um `upgrade` que deu certo não imprime nada.
- Na Railway, o pré-deploy roda `alembic upgrade head` antes do `bootstrap_admin` e da semente ([seção 22.1](../../../docs/sdd/entrega.md#221-railway)).

## Cuidados

- **Expand and contract.** Uma revisão nunca quebra a versão anterior do código, como a `0009`, que acrescenta uma coluna anulável. Uma coluna só sai no deploy seguinte ao que parou de usá-la ([seção 22.1](../../../docs/sdd/entrega.md#221-railway)).
- **Rollback com migração.** Uma versão que trouxe revisão não volta pela Railway: o `alembic upgrade head` da versão anterior não conhece a revisão nova do banco, e o pré-deploy falha. A saída é corrigir para frente ([seção 22.3](../../../docs/sdd/entrega.md#223-github-actions)). Para saber se houve revisão entre duas versões, use `git diff --stat <anterior> <novo> -- apps/api/alembic/versions`. O passo 2 de [`docs/rollback.md`](../../../docs/rollback.md) ainda aponta para `apps/api/migrations`, que não existe; é o débito da Etapa 11.2.
- **Constantes do código.** `0002`, `0004`, `0005` e `0007` importam listas e números de `app.domain` e `app.models`. Um banco criado do zero recebe o valor de hoje, mas um banco que já existe não muda sozinho: um desfecho, uma finalidade ou um status novo pede uma revisão que troque a restrição, e mudar a dimensão do vetor pede uma revisão e um re-embedding completo ([seção 8.3](../../../docs/sdd/arquitetura.md#83-texto-de-embedding)).
- **Índices pendentes.** A Etapa 13.5 cria os índices de `conversations.guest_key_id` e `auth_sessions.user_id` e tira o `messages_conversation_id_idx`, que repete a restrição única.

## Testes

- [`tests/integration/conftest.py`](../tests/integration/conftest.py): a fixture `migrated_database` roda `upgrade head` duas vezes no banco local, e a segunda não faz nada.
- [`tests/integration/test_database.py`](../tests/integration/test_database.py): confere colunas, restrições e a revisão `0011_whatsapp` no topo, e refaz `downgrade 0001_initial` seguido de `upgrade head`.
- A CI roda os dois contra o contêiner `pgvector/pgvector:pg18` ([seção 21.1](../../../docs/sdd/entrega.md#211-ci-padrão)).

## Leia também

- [SDD 8.1, tabelas](../../../docs/sdd/arquitetura.md#81-tabelas) e [8.2, índices](../../../docs/sdd/arquitetura.md#82-índices-e-o-predicado-de-busca)
- [SDD 11.6, retenção e eliminação](../../../docs/sdd/lgpd.md#116-retenção-e-eliminação)
- [SDD 22.1, Railway e expand and contract](../../../docs/sdd/entrega.md#221-railway)
- [`app/db`](../app/db/README.md), a sessão que o `env.py` também usa
- Guia: [parte 9, dados, transações e migrações](../../../docs/guia/09-dados-e-migracoes.md) e [parte 14, entrega e operação](../../../docs/guia/14-entrega-e-operacao.md)
