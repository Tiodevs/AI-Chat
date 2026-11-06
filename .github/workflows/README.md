# workflows

GitHub Actions. Seção 22.3 do SDD.

| Workflow | O que faz |
|---|---|
| `ci.yml` | `api` (Ruff, mypy e Pytest contra `pgvector/pgvector:pg18`), `web` (ESLint, tipos, Vitest, Playwright com respostas simuladas, build e Storybook), `contract` (OpenAPI e tipos iguais aos commitados) e `e2e` (jornadas contra a API real no adaptador `demo`, com axe e CSP) |
| `evals.yml` | Sincroniza `evals/public_qa.jsonl` com o LangSmith e comenta o resultado na pull request |
| `deploy.yml` | Depois da CI verde na `main`: development, aprovação e production na Railway e na Vercel, com os testes de fumaça de `.github/scripts/smoke.mjs` |

O `deploy.yml` só roda com a variável de repositório `DEPLOY_ENABLED` igual a `true` e com os segredos e variáveis de cada GitHub Environment, listados no topo do arquivo.
