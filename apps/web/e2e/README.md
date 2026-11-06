# e2e

Testes de ponta a ponta com Playwright. Seção 21.1 do SDD.

| Suíte | Configuração | Backend |
|---|---|---|
| `e2e/*.spec.ts` | `playwright.config.ts` | Respostas da API simuladas por `page.route`, com `pnpm dev` |
| `e2e/live/*.spec.ts` | `playwright.live.config.ts` | API de verdade no adaptador `demo`, com `vite preview` e os cabeçalhos de produção |

A suíte com a API precisa de um PostgreSQL com pgvector vazio ou descartável. Ela roda as migrações, cria o admin de teste e semeia o corpus antes de subir a API:

```bash
DATABASE_URL=postgresql://atrium:atrium@127.0.0.1:5432/atrium_e2e pnpm exec playwright test -c playwright.live.config.ts
```
