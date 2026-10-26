# web

Frontend do Atrium. React 19, Vite, Tailwind e shadcn/ui. Seção 13 do SDD.

## Como rodar

Na pasta `apps/web`:

1. `pnpm install`
2. `pnpm dev` abre `http://localhost:5173`
3. `pnpm test` roda Vitest
4. `pnpm storybook` abre o catálogo em `http://localhost:6006`

O Vite encaminha `/backend` para `http://127.0.0.1:8000`. A API precisa estar no ar só quando uma tela chama o servidor. A casca desta etapa não chama a API.
