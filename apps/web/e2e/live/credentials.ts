/**
 * Credenciais do admin da suíte ao vivo. Seções 10.5 e 21.1 do SDD.
 *
 * O `playwright.live.config.ts` passa este par à API como `ADMIN_EMAIL` e
 * `ADMIN_PASSWORD`, e o `bootstrap_admin` cria o admin no banco vazio. O
 * `signInAsAdmin` de `fixtures.ts` entra com ele. Num banco que já tem outro
 * admin, o script ignora o par (seção 10.5), e a entrada do admin falha.
 */

/**
 * Admin da e2e com a API: valores de teste de um banco que só existe durante
 * a e2e. `E2E_ADMIN_EMAIL` e `E2E_ADMIN_PASSWORD` trocam os valores padrão.
 */
export const e2eAdmin = {
  email: process.env.E2E_ADMIN_EMAIL ?? "admin.e2e@example.com",
  password: process.env.E2E_ADMIN_PASSWORD ?? "Atrium-e2e-admin-2026",
}
