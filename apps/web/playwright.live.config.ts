/**
 * Jornadas contra a API de verdade. Seções 21.1 e 22.3 do SDD (job `e2e` do `ci.yml`).
 *
 * Sobe a API com o adaptador `demo` (regras, sem modelo) sobre um PostgreSQL com pgvector,
 * e o frontend com `vite preview`, o mesmo proxy de `/backend` e os cabeçalhos de produção.
 * Precisa de `DATABASE_URL` apontando para um banco vazio ou descartável.
 *
 * As chaves abaixo são valores de teste de um banco que existe só durante a e2e.
 *
 * Quem usa: `pnpm exec playwright test -c playwright.live.config.ts` e o
 * job `e2e` do `ci.yml`. Os testes ficam em `e2e/live` e estão listados em
 * `e2e/README.md`.
 */
import { defineConfig, devices } from "@playwright/test"

import { e2eAdmin } from "./e2e/live/credentials.ts"

const apiPort = 8000
const webPort = 4173
const webOrigin = `http://127.0.0.1:${webPort}`

const databaseUrl = process.env.DATABASE_URL ?? ""
if (!databaseUrl) {
  throw new Error("Defina DATABASE_URL com um PostgreSQL com pgvector para a e2e com a API.")
}

/**
 * O ambiente da API nesta suíte. Com `APP_ENV` `test`, a API não exige o
 * segredo da borda, e o proxy do Vite não o manda (seção 10.3).
 * `WEB_ORIGIN` é a origem do `vite preview`, que a API compara com o
 * `Origin` dos pedidos que mudam estado. O teto de tokens `0` fica
 * desligado, o que só vale em `local` e `test` (seção 7.1).
 */
const apiEnv: Record<string, string> = {
  APP_ENV: "test",
  APP_AI_ADAPTER: "demo",
  GEMINI_API_KEY: "",
  DATABASE_URL: databaseUrl,
  WEB_ORIGIN: webOrigin,
  RATE_LIMIT_HMAC_KEY: "e2e-rate-limit-key",
  PSEUDONYM_KEY: "e2e-pseudonym-key",
  METRICS_TOKEN: "e2e-metrics-token",
  ADMIN_EMAIL: e2eAdmin.email,
  ADMIN_PASSWORD: e2eAdmin.password,
  PRIVACY_CONTACT_EMAIL: "privacidade@harborlight.example",
  // O embedding lexical do modo demo separa bem acima de 0,3; o Gemini usa 0,50.
  RETRIEVAL_MIN_SIMILARITY: "0.3",
  LLM_DAILY_TOKEN_BUDGET: "0",
  LANGSMITH_TRACING: "false",
  LOG_LEVEL: "WARNING",
}

export default defineConfig({
  testDir: "./e2e/live",
  // Um teste por vez: todos dividem a mesma API e o mesmo banco.
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  // O backend é determinístico: uma nova tentativa só esconderia um defeito.
  retries: 0,
  timeout: 60_000,
  use: {
    baseURL: webOrigin,
    trace: "retain-on-failure",
  },
  // Os dois servidores sobem antes dos testes. O Playwright espera cada
  // `url` responder, por até 4 minutos.
  webServer: [
    {
      // A API, em `apps/api`: migrações, o admin de teste e a semente do
      // corpus, e só então o Uvicorn. A espera é pelo `/ready`.
      command:
        "uv run alembic upgrade head && uv run python -m app.scripts.bootstrap_admin && " +
        `uv run python -m app.scripts.seed && uv run uvicorn app.main:app --host 127.0.0.1 --port ${String(apiPort)}`,
      cwd: "../api",
      url: `http://127.0.0.1:${String(apiPort)}/ready`,
      env: apiEnv,
      timeout: 240_000,
      reuseExistingServer: !process.env.CI,
      stdout: "ignore",
      stderr: "pipe",
    },
    {
      // O build de produção no `vite preview`, com o proxy de `/backend`
      // apontado para a API acima. `--strictPort` falha se a porta estiver
      // ocupada, em vez de escolher outra.
      command: `pnpm build && pnpm exec vite preview --host 127.0.0.1 --port ${String(webPort)} --strictPort`,
      url: webOrigin,
      env: { API_PROXY_TARGET: `http://127.0.0.1:${String(apiPort)}` },
      timeout: 240_000,
      reuseExistingServer: !process.env.CI,
    },
  ],
  projects: [
    {
      // Celular com movimento reduzido: todas as jornadas, menos a de
      // teclado.
      name: "live",
      testIgnore: /keyboard[.]live[.]spec[.]ts/,
      use: { ...devices["Pixel 5"], reducedMotion: "reduce" },
    },
    {
      // A auditoria também roda no desktop e sem redução de movimento (Etapa 9.1).
      name: "live-desktop",
      testMatch: /(audit|keyboard)[.]live[.]spec[.]ts/,
      use: { ...devices["Desktop Chrome"], reducedMotion: "no-preference" },
    },
  ],
})
