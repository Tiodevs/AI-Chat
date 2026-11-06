/** Admin da e2e com a API: valores de teste de um banco que só existe durante a e2e. */
export const e2eAdmin = {
  email: process.env.E2E_ADMIN_EMAIL ?? "admin.e2e@example.com",
  password: process.env.E2E_ADMIN_PASSWORD ?? "Atrium-e2e-admin-2026",
}
