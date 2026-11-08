# Parte 2 · Rodar e explorar

> **Você vai entender:** os jeitos de subir o projeto, como a configuração é lida, o que muda entre os adaptadores de IA e as ferramentas para ver o sistema por dentro.
>
> **Leia antes:** [parte 1](01-mapa-do-sistema.md). **Tempo:** 45 minutos, mais a instalação.

## 1. Três jeitos de rodar

| Jeito | Sobe | Precisa | Bom para |
|---|---|---|---|
| **A. Direto na máquina** | API e frontend, com o banco de development da Railway | Python 3.12, [uv](https://docs.astral.sh/uv/), Node 22 ou mais, [pnpm](https://pnpm.io/) e a `DATABASE_URL` de development | O dia a dia. É o caminho da especificação: o desenvolvimento local não exige Docker (NFR-4) |
| **B. Tudo em Docker** | Banco, API, frontend, Prometheus e Grafana | Docker | Explorar sem conta em lugar nenhum, ver métricas e painéis, ter um banco descartável |
| **C. Só o catálogo** | Storybook | Node e pnpm | Estudar os componentes sem API |

Dá para misturar: o banco do Docker com a API e o frontend direto na máquina. É assim que os testes de integração rodam localmente (parte 13).

## 2. Jeito A, passo a passo

### API

Em `apps/api`:

1. Copie `.env.example` para `.env`. O `.env` não vai para o Git.
2. Preencha o mínimo (seção 4 abaixo): `DATABASE_URL`, `RATE_LIMIT_HMAC_KEY` e `PSEUDONYM_KEY`, mais o adaptador de IA.
3. Instale as dependências:

```bash
uv sync
```

4. Aplique as migrações:

```bash
uv run alembic upgrade head
```

5. Crie o admin, com `ADMIN_EMAIL` e `ADMIN_PASSWORD` no `.env`:

```bash
uv run python -m app.scripts.bootstrap_admin
```

6. Carregue os 12 documentos do corpus. O embedding usa o adaptador escolhido, então semeie com o mesmo `APP_AI_ADAPTER` que você vai usar para perguntar:

```bash
uv run python -m app.scripts.seed
```

7. Suba a API, que recarrega a cada mudança de arquivo:

```bash
uv run uvicorn app.main:app --reload
```

8. Abra `http://127.0.0.1:8000/health` (responde sem banco) e `http://127.0.0.1:8000/ready` (responde 200 quando o banco responde, a extensão `vector` existe e a dimensão do embedding bate com a coluna).

> [!TIP]
> Se o `uv` não estiver no PATH mas foi instalado com o `pip`, use `python -m uv` no lugar de `uv` em todos os comandos.

### Frontend

Em `apps/web`:

```bash
pnpm install
```

```bash
pnpm dev
```

Abra `http://localhost:5173`. O Vite encaminha `/backend` para `http://127.0.0.1:8000`. Para apontar para outra API, defina `API_PROXY_TARGET` antes do `pnpm dev`.

## 3. Jeito B, tudo em Docker

Na raiz do repositório:

```bash
docker compose up --build
```

O serviço `api` do [`docker-compose.yml`](../../docker-compose.yml) aplica as migrações, cria o admin, semeia o corpus e só então sobe o uvicorn. O compose já traz valores locais para as chaves, e o adaptador de IA padrão é `fake`, então não precisa de chave nenhuma.

> [!IMPORTANT]
> Com o `fake`, **toda pergunta recebe a resposta de indisponibilidade**, porque o falso só responde o que um teste programou (seção 5 abaixo). Para explorar o produto sem chave, crie um `.env` na raiz com `APP_AI_ADAPTER=demo` antes do primeiro `docker compose up`. Se o banco já foi semeado com outro adaptador, apague os volumes com `docker compose down -v`: a semente pula os documentos que não mudaram e deixaria os vetores do adaptador antigo.

| Serviço | Endereço | Acesso |
|---|---|---|
| Frontend | http://localhost:5173 | |
| API | http://127.0.0.1:8000 | admin `admin@example.com` / `Atrium-local-2026-admin`, ou o que estiver em `ADMIN_EMAIL` e `ADMIN_PASSWORD` |
| Prometheus | http://localhost:9090 | Os alvos ficam em `/targets` |
| Grafana | http://localhost:3000 | `admin` / `admin` |
| PostgreSQL | `postgresql://atrium:atrium@127.0.0.1:5432/atrium` | |

Detalhes que confundem:

- Com o `fake`, o cadastro por conversa também falha: cada mensagem responde 503 e a tela mostra o aviso de indisponível. O formulário, a conta e o admin funcionam.
- Para usar o Gemini, crie um `.env` **na raiz** com `APP_AI_ADAPTER=gemini` e `GEMINI_API_KEY`.
- O admin só é criado quando o banco não tem nenhum. Para trocar `ADMIN_EMAIL` depois, apague os volumes com `docker compose down -v`.
- `/metrics` pede o token `local-metrics-token`.
- `docker compose down` para tudo e mantém os dados; `docker compose down -v` apaga os volumes.

## 4. A configuração

A configuração inteira é a classe `Settings`, em [`app/core/config.py`](../../apps/api/app/core/config.py). Ela usa o pydantic-settings: cada campo vira uma variável de ambiente com o nome em maiúsculas (`database_url` → `DATABASE_URL`), e o arquivo `.env` só é lido se existir na pasta de onde o processo sobe. Por isso os comandos rodam de dentro de `apps/api`.

Cada variável está comentada em [`apps/api/.env.example`](../../apps/api/.env.example), que é a referência. Um teste ([`test_layout.py`](../../apps/api/tests/unit/test_layout.py)) garante que esse arquivo lista exatamente os campos de `Settings` e que os segredos vêm vazios.

### O mínimo para cada coisa

| Para | Você precisa de |
|---|---|
| Ver `/health` | Nada |
| Ver `/ready` | `DATABASE_URL` |
| Perguntar, entrar, cadastrar ou enviar documento | `RATE_LIMIT_HMAC_KEY`. Vazia, esses serviços levantam `RuntimeError` e a rota responde 500, porque os limites de taxa usam HMAC (seção 10.4) |
| Abrir o inspetor de qualidade do admin e ter o assunto pseudonimizado nos rastros | `PSEUDONYM_KEY`. Vazia, o inspetor responde 500 |
| Respostas do Gemini | `APP_AI_ADAPTER=gemini` e `GEMINI_API_KEY`. Sem a chave, as perguntas recebem a resposta de indisponibilidade |
| Entrar como admin | `ADMIN_EMAIL` e `ADMIN_PASSWORD`, e depois `bootstrap_admin`. Elas só são lidas enquanto não existe nenhum admin |
| Ver `/metrics` | `METRICS_TOKEN`, enviado como `Authorization: Bearer <token>`. Sem ele, a rota responde 404 |
| Rastros no LangSmith | `LANGSMITH_TRACING=true` e `LANGSMITH_API_KEY` |

Para gerar um valor aleatório para as chaves:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Três regras que a configuração impõe

1. **A URL do banco é reescrita.** `postgresql://` vira `postgresql+asyncpg://` (`rewrite_database_url`), porque o SQLAlchemy assíncrono precisa do driver asyncpg. Você cola a URL da Railway como ela vem.
2. **O adaptador `demo` não sai da máquina.** Com `APP_ENV` `development` ou `production`, `APP_AI_ADAPTER=demo` é recusado na leitura da configuração (`_demo_only_off_the_cloud`).
3. **Os ambientes da Railway exigem as proteções.** Em `development` e `production`, `create_app` chama `require_safeguards`: sem `LLM_DAILY_TOKEN_BUDGET` maior que zero e sem `RATE_LIMIT_HMAC_KEY`, `PSEUDONYM_KEY` e `EDGE_SECRET`, a API não sobe e o erro lista o que falta. A conferência fica na subida da API, e não em `Settings`, porque o `retention-job` lê a mesma configuração sem essas variáveis.

## 5. Os adaptadores de IA

`APP_AI_ADAPTER` escolhe, num lugar só, quem responde pelo chat e pelo embedding. É o padrão Strategy da seção 6.2: o resto do código fala com as portas e não sabe qual adaptador está por trás.

| Valor | Chat | Embedding | Quando usar |
|---|---|---|---|
| `gemini` (padrão) | `GeminiChatProvider` | `GeminiEmbeddingProvider` | Para ver o produto de verdade. Sem `GEMINI_API_KEY`, os dois viram os provedores indisponíveis, que degradam na chamada |
| `fake` | `FakeChatProvider` | `DeterministicEmbeddingProvider` | Testes automáticos. O chat só devolve o que o teste programou com `script(...)`; sem roteiro, levanta `ProviderUnavailable`, e a pergunta termina em `error`. O vetor é um hash do texto, então textos parecidos não ficam próximos |
| `demo` | `DemoChatProvider` | `LexicalEmbeddingProvider` | A suíte e2e com a API real ([ADR-014](../adr/014-adaptador-demo.md)) e a demonstração local sem chave. Classifica por palavras (sintoma e remédio viram orientação médica), responde com a primeira frase do melhor trecho e a citação dele, e conduz o cadastro por conversa com as perguntas fixas. O vetor junta as palavras do texto, então a busca acha o trecho certo |

A escolha acontece em [`chat_factory.py`](../../apps/api/app/adapters/chat_factory.py) e [`embedding_factory.py`](../../apps/api/app/adapters/embedding_factory.py). O [README dos adaptadores](../../apps/api/app/adapters/README.md) detalha cada um.

## 6. Scripts para explorar

Os comandos de [`app/scripts`](../../apps/api/app/scripts/README.md) rodam em `apps/api`, com `uv run python -m app.scripts.<nome>`. Os que mais ensinam:

| Comando | O que você aprende com ele |
|---|---|
| `search "Qual é o horário de visita?"` | O que a busca híbrida devolve para uma pergunta, com a similaridade de cada chunk (parte 5) |
| `ask "Onde posso estacionar?"` | O pipeline de perguntas inteiro sem HTTP: desfecho, citações e texto (parte 4) |
| `seed` | A ingestão do corpus. Rodar de novo não embeda o que não mudou (FR-13) |
| `retention` | Quantas linhas cada regra de retenção apagaria hoje (parte 8) |
| `export_openapi` | Gera o contrato que o frontend usa (parte 11) |

O [README dos scripts](../../apps/api/app/scripts/README.md) tem todos, com os argumentos.

## 7. Ver o sistema por dentro

| Onde | O que mostra |
|---|---|
| Terminal da API | Uma linha JSON por pedido, com `request_id`, rota, status e duração (parte 10) |
| http://127.0.0.1:8000/docs | A documentação interativa que o FastAPI gera do código, com todos os endpoints e schemas |
| `curl -N http://127.0.0.1:8000/v1/diagnostics/stream` | Um fluxo SSE de teste: três eventos `tick`, um por segundo. É o que a fumaça usa para conferir que o fluxo não fica preso no caminho |
| `pnpm storybook`, em `apps/web` | O catálogo dos componentes em http://localhost:6006, com o painel de acessibilidade |
| `psql` no banco | As tabelas da parte 9. Comece com `select title, status from documents;` |

### Uma pergunta pelo terminal

Ver a resposta crua ajuda a entender a parte 4. Com a API local no ar, crie uma conversa de convidado. Pedidos que mudam estado precisam do cabeçalho `Origin` igual ao `WEB_ORIGIN`, e o cookie de convidado fica em `cookies.txt`:

```bash
curl -s -c cookies.txt -X POST -H "Origin: http://localhost:5173" http://127.0.0.1:8000/v1/conversations
```

Copie o `id` da resposta e mande uma pergunta. O `-N` mostra os eventos à medida que chegam:

```bash
curl -N -b cookies.txt -X POST -H "Origin: http://localhost:5173" -H "Content-Type: application/json" -d "{\"text\": \"Qual é o horário de visita?\", \"client_message_id\": \"$(python -c 'import uuid; print(uuid.uuid4())')\"}" http://127.0.0.1:8000/v1/conversations/<id>/messages
```

Você vai ver `event: meta`, depois vários `event: token`, um `event: citation` por fonte e `event: done` com o desfecho. A [parte 4](04-pergunta-de-ponta-a-ponta.md) explica cada um.

## 8. Problemas comuns

| Sintoma | Causa provável |
|---|---|
| `/ready` responde 503 | Banco inacessível, extensão `vector` ausente ou `EMBEDDING_DIMENSIONS` diferente da coluna `vector(768)` |
| Login, pergunta ou cadastro respondem 500 | `RATE_LIMIT_HMAC_KEY` vazia |
| Toda pergunta recebe "temporariamente indisponível" | Adaptador `fake` (o padrão do Docker), `APP_AI_ADAPTER=gemini` sem `GEMINI_API_KEY`, orçamento do dia estourado ou circuito aberto depois de 5 falhas seguidas (parte 7) |
| Toda pergunta se abstém | O corpus não foi semeado, ou foi semeado com outro adaptador de embedding |
| A API não sobe e cita `APP_ENV=development exige ...` | Faltam as proteções dos ambientes da Railway (seção 4 acima) |
| 403 `bad_origin` num `curl` | Falta o cabeçalho `Origin` num pedido que muda estado |
| 403 `bad_origin` no navegador | O app foi aberto num endereço diferente do `WEB_ORIGIN`, como `http://127.0.0.1:5173` em vez de `http://localhost:5173`. O proxy do Vite troca o `Host`, mas o `Origin` chega à API como o navegador mandou |
| A porta 8000 já está em uso | O `api` do Docker está no ar. Pare-o ou suba o uvicorn com `--port 8001` e defina `API_PROXY_TARGET` |

## Para praticar

1. Suba a API sem `.env` e abra `/health` e `/ready`. Explique por que uma responde e a outra não.
2. Rode `search` e `ask` com a mesma pergunta e compare: quais chunks a busca trouxe e quais viraram citação.
3. Faça a pergunta pelo terminal da seção 7 e copie o `request_id` do evento `meta`. Ache a mesma linha no log da API.
4. No Docker, suba com o `fake` e faça uma pergunta. Depois rode `docker compose down -v`, suba com `APP_AI_ADAPTER=demo` e pergunte de novo. Explique a diferença com a tabela da seção 5.

**Próxima:** [Parte 3 · A API por dentro](03-api-por-dentro.md)
