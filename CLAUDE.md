# Atrium

Assistente público para visitantes do hospital fictício Harborlight General Hospital. Monorepo com API em `apps/api` (FastAPI, LangGraph, Postgres com pgvector) e frontend em `apps/web` (React, Vite, shadcn/ui, GSAP).

A especificação é `docs/sdd.md` (seções em `docs/sdd/`). A implementação segue `docs/plano-de-acao.md`, em etapas com aprovação a cada entrega. A especificação vem antes do código: cite a seção que a tarefa implementa e atualize o SDD na mesma mudança quando o comportamento mudar.

## Comandos

API (em `apps/api`, sem Docker, banco na Railway; veja o `README.md`):

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
uv run ruff check && uv run mypy && uv run pytest
```

Frontend (em `apps/web`):

```bash
pnpm install
pnpm dev
pnpm exec eslint . && pnpm test
pnpm exec tsc --noEmit -p tsconfig.app.json && pnpm exec tsc --noEmit -p tsconfig.node.json
pnpm build && pnpm build-storybook
```

E2E: `pnpm exec playwright test`. A CI (`.github/workflows/ci.yml`) roda tudo isso.

## Convenções

- Texto visível ao usuário em português (`apps/web/src/i18n/pt.ts`, `apps/api/app/prompts`). Código, rotas e identificadores em inglês.
- Testes automáticos nunca chamam Gemini nem LangSmith. Use `FakeChatProvider`, `DeterministicEmbeddingProvider` e `NoopFeedbackSink`.
- Nunca commite `.env`, credenciais nem `.claude/settings.local.json`.

## Onde estão as regras

- `.claude/rules/commits-e-push.md`: commits atômicos e push ao fim de toda tarefa que altera arquivos. Sempre carregada.
- `.claude/rules/camadas.md`: camadas da API (SDD 6.2). Carrega ao tocar `apps/api/**/*.py`.
- `.claude/rules/design-system.md`: design system (SDD 14.8). Carrega ao tocar `.tsx` e `.css` de `apps/web`.
- `.claude/rules/gsap.md`: movimento com GSAP (SDD 16.5). Carrega ao tocar `.ts` e `.tsx` de `apps/web`.
- `.claude/skills/definicao-de-pronto/`: DP-1 a DP-9. Use ao implementar, revisar ou encerrar uma etapa e ao abrir a PR dela.
