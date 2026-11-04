FROM node:22-alpine

RUN corepack enable
WORKDIR /app

COPY apps/web/package.json apps/web/pnpm-lock.yaml apps/web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY apps/web ./

EXPOSE 5173
CMD ["pnpm", "dev", "--host", "0.0.0.0"]
