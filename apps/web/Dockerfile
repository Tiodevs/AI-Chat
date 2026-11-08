# O frontend em modo de desenvolvimento, só para o serviço `web` do docker-compose.yml.
# Contexto de build: a raiz do repositório. Esta imagem não é publicada: a Vercel recebe o
# build que o deploy.yml faz com `vercel build` (seção 22.2).
FROM node:22-alpine

# O corepack traz o pnpm. Sem `packageManager` no package.json, a versão do pnpm não é fixa.
RUN corepack enable
WORKDIR /app

# Primeiro só os manifestos, numa camada que o cache do Docker reaproveita enquanto o lockfile
# não muda. O pnpm-workspace.yaml diz quais dependências podem rodar scripts de build.
COPY apps/web/package.json apps/web/pnpm-lock.yaml apps/web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

# Depois o código. O .dockerignore da raiz deixa de fora node_modules, dist e a pasta e2e.
COPY apps/web ./

# `--host 0.0.0.0` faz o Vite aceitar conexões de fora do contêiner. O proxy de /backend vai
# para `API_PROXY_TARGET`, que o docker-compose.yml aponta para o serviço `api`.
EXPOSE 5173
CMD ["pnpm", "dev", "--host", "0.0.0.0"]
