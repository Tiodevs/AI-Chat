import { expect, test as base, type Page } from "@playwright/test"

import { pt } from "../../src/i18n/pt.ts"
import { e2eAdmin } from "./credentials.ts"

export { expectNoSeriousViolations } from "../api.ts"

/**
 * Cada teste falha se o navegador recusar algo pela CSP da seção 13.4: o `vite preview`
 * manda os mesmos cabeçalhos da Vercel.
 */
export const test = base.extend<{ cspViolations: string[] }>({
  cspViolations: [
    async ({ page }, use) => {
      const violations: string[] = []
      page.on("console", (message) => {
        if (message.type() === "error" && /Content Security Policy/i.test(message.text())) {
          violations.push(message.text())
        }
      })
      await use(violations)
      expect(violations, "violações de CSP no console").toEqual([])
    },
    { auto: true },
  ],
})

export { expect }

export function uniqueEmail(prefix: string) {
  return `${prefix}.${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}@example.com`
}

export async function signIn(page: Page, email: string, password: string) {
  await page.goto("/sign-in")
  await page.getByLabel(pt.signIn.email).fill(email)
  await page.getByLabel(pt.signIn.password).fill(password)
  await page.getByRole("button", { name: pt.signIn.submit }).click()
}

export async function signInAsAdmin(page: Page, returnTo = "/admin/privacy") {
  await page.goto(`/sign-in?returnTo=${encodeURIComponent(returnTo)}`)
  await page.getByLabel(pt.signIn.email).fill(e2eAdmin.email)
  await page.getByLabel(pt.signIn.password).fill(e2eAdmin.password)
  await page.getByRole("button", { name: pt.signIn.submit }).click()
  // O admin criado pelo script ainda não aceitou os Termos: passa pelo novo aceite (SDD 13.3).
  await expect(page).toHaveURL(/\/legal\/accept/)
  await page.getByRole("button", { name: pt.legalAccept.accept }).click()
  await expect(page).toHaveURL(new RegExp(`${returnTo}$`))
}

/** Cria um membro pelo formulário, como na J4, e volta com a sessão aberta. */
export async function registerByForm(page: Page, email: string, name = "Ana Costa") {
  await page.goto("/register/form")
  await page.getByLabel(pt.registration.fields.full_name).fill(name)
  await page.getByLabel(pt.registration.fields.email).fill(email)
  await page
    .getByRole("textbox", { name: pt.registration.fields.password, exact: true })
    .fill("senha-segura-1")
  await page.getByRole("checkbox", { name: pt.registration.terms }).check()
  await page.getByRole("checkbox", { name: pt.registration.age }).check()
  await page.getByRole("button", { name: pt.registration.createAccount }).click()
  await expect(page.getByRole("heading", { name: pt.pages.account })).toBeVisible()
}
