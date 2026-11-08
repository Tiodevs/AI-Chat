/**
 * A suíte de ponta a ponta com a API simulada, a do job `web` da CI
 * (seções 15.8 e 21.1).
 *
 * Sobe o `pnpm dev` na porta 4173 e roda os testes de `e2e`. Os testes
 * respondem aos pedidos de `/backend/v1` com `page.route`, dentro do
 * navegador, então nenhuma API precisa estar no ar. A suíte com a API de
 * verdade fica em `playwright.live.config.ts`.
 *
 * Quem usa: `pnpm exec playwright test` (`pnpm e2e`) e o job `web` do
 * `ci.yml`. Os testes estão listados em `e2e/README.md`.
 */
import { defineConfig, devices } from "@playwright/test"

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  // Na CI, um `test.only` esquecido reprova a execução, e uma falha ganha
  // uma nova tentativa, com rastro gravado só nela.
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "on-first-retry",
  },
  // Fora da CI, reaproveita um servidor que já esteja na porta.
  webServer: {
    command: "pnpm dev --host 127.0.0.1 --port 4173",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: !process.env.CI,
  },
  // As jornadas rodam num celular com movimento reduzido, para capturas
  // estáveis, e `motion.spec.ts` roda uma vez no desktop sem redução, para
  // pegar erro de animação (seção 16.6).
  projects: [
    {
      name: "mobile",
      // e2e/live roda com a API de verdade, em playwright.live.config.ts.
      testIgnore: ["**/motion.spec.ts", "**/e2e/live/**"],
      use: {
        ...devices["Pixel 5"],
        reducedMotion: "reduce",
      },
    },
    {
      name: "animation",
      testMatch: /motion\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        reducedMotion: "no-preference",
      },
    },
  ],
})
