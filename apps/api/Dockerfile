# Contexto de build: a raiz do repositório (a semente lê content/corpus).
#
# A imagem da API. Serve aos serviços `api` e `retention-job` da Railway, publicados pelo
# deploy.yml com `railway up`, e ao serviço `api` do docker-compose.yml: a imagem local e a de
# produção são uma só (seção 22.1, ADR-013). O .dockerignore da raiz tira do contexto os
# testes, a documentação e os arquivos .env.
#
# O contêiner roda como root, e a base não está fixada por digest. A Etapa 15.2 troca para um
# usuário sem privilégio e fixa a base.
FROM python:3.12-slim

# Só o binário do uv, da imagem oficial, na versão fixa.
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv

# Bytecode compilado na instalação, cópia em vez de link para o cache do uv, logs JSON direto
# na stdout sem buffer (seção 18.1) e o ambiente virtual primeiro no PATH, para o pré-deploy
# chamar `alembic` e `python` e o CMD chamar `opentelemetry-instrument` sem `uv run`.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH=/repo/apps/api/.venv/bin:$PATH

# O caminho imita o repositório: `scripts/seed.py` acha o corpus quatro pastas acima, em
# /repo/content/corpus.
WORKDIR /repo/apps/api

# Primeiro só as dependências, numa camada que o cache do Docker reaproveita enquanto o
# `uv.lock` não muda. `--no-dev` deixa de fora pytest, Ruff e mypy.
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Depois o código, as migrações e o corpus. O `app/BUILD_SHA` que o deploy.yml grava entra
# junto com `app` (seção 12, `GET /health`). O segundo `uv sync` instala o próprio projeto.
COPY apps/api/app ./app
COPY apps/api/alembic ./alembic
COPY apps/api/alembic.ini ./
COPY content /repo/content
RUN uv sync --frozen --no-dev

# Só documenta a porta padrão. Na Railway, `PORT` vale 8080 (seção 22.1).
EXPOSE 8000
# Na Railway a porta vem em $PORT. Ambientes criados depois de 16/10/2025 resolvem a rede
# privada também em IPv4, e o asyncio abre `::` só em IPv6; por isso 0.0.0.0.
# O docker-compose.yml define o próprio comando. Seção 22.1 do SDD.
# O `sh -c` expande `$PORT`, e o `exec` troca o shell pelo processo, que recebe o sinal de
# parada. O `opentelemetry-instrument` carrega o SDK antes de FastAPI, SQLAlchemy, asyncpg e
# httpx (seção 18.2). `--proxy-headers` com `--forwarded-allow-ips='*'` aceita o
# `x-forwarded-for` de qualquer origem. Como a API recusa /v1 sem o segredo da borda em
# development e production, o IP dos limites vem da Vercel (seções 10.3 e 10.4).
CMD ["sh", "-c", "exec opentelemetry-instrument uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
