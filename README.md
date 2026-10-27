# Atrium

Assistente público para visitantes do hospital fictício Harborlight General Hospital.

A especificação pronta para implementação está em [docs/sdd.md](docs/sdd.md).

A implementação segue o [plano de ação](docs/plano-de-acao.md), em etapas com critérios de aceite e aprovação a cada entrega.

## Como rodar localmente

A API roda direto na máquina. Docker não é necessário. O banco é o PostgreSQL de development na Railway, com a extensão `vector`.

1. Entre em `apps/api`.
2. Copie `.env.example` para `.env` e preencha `DATABASE_URL` com a URL pública do ambiente `development`. O `.env` não vai para o Git.
3. Instale as dependências com `uv sync`.
4. Aplique as migrações com `uv run alembic upgrade head`.
5. Suba a API com `uv run uvicorn app.main:app --reload`.
6. Abra `http://127.0.0.1:8000/health` e `http://127.0.0.1:8000/ready`. `/health` responde 200 sem o banco. `/ready` responde 200 quando o banco responde e a extensão `vector` está instalada.

O frontend fica em `apps/web`.

1. Entre em `apps/web`.
2. Instale as dependências com `pnpm install`.
3. Suba a casca com `pnpm dev` e abra `http://localhost:5173`.
