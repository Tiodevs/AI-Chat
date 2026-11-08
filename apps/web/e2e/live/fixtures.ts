/**
 * Fixtures e helpers da suíte ao vivo. Seções 10.4, 13.3, 13.4 e 21.1 do SDD.
 *
 * Os specs de `live/` importam daqui o `test`, com duas fixtures automáticas:
 * um IP de visitante por teste e a checagem de CSP. Os helpers criam um
 * membro pelo formulário e entram como admin. Nenhum teste limpa o banco da
 * e2e, então cada conta nova usa um e-mail único.
 */
import { expect, test as base, type Page } from "@playwright/test"

import { pt } from "../../src/i18n/pt.ts"
import { e2eAdmin } from "./credentials.ts"

// O mesmo axe da suíte simulada.
export { expectNoSeriousViolations } from "../api.ts"

/**
 * Contador que dá a cada teste um IP diferente em `visitorAddress`. Ele
 * recomeça em cada processo, então uma rodada nova repete os mesmos IPs.
 */
let visitor = 0

/**
 * O `test` do Playwright com as fixtures da suíte ao vivo. As duas são
 * `auto`: valem em todo teste, sem o teste pedir.
 */
export const test = base.extend<{ cspViolations: string[]; visitorAddress: string }>({
  // Cada teste é um visitante diferente. Sem isso, a suíte inteira divide o mesmo IP e passa
  // dos limites da seção 10.4 (20 envios de cadastro por hora). A faixa 198.18.0.0/15 é a
  // reservada para testes de rede.
  visitorAddress: [
    async ({ page }, use) => {
      visitor += 1
      const address = `198.18.${String(Math.floor(visitor / 250))}.${String((visitor % 250) + 1)}`
      await page.setExtraHTTPHeaders({ "X-Forwarded-For": address })
      await use(address)
    },
    { auto: true },
  ],
  // Cada teste falha se o navegador recusar algo pela CSP da seção 13.4: o
  // `vite preview` manda os mesmos cabeçalhos da Vercel. O Chrome registra a
  // recusa como erro no console, e a conferência roda depois do teste.
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

/**
 * Um e-mail novo a cada chamada: o prefixo, o relógio e um sufixo aleatório.
 * O e-mail é único em `users` (seção 8.1), e nenhum teste limpa o banco.
 */
export function uniqueEmail(prefix: string) {
  return `${prefix}.${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}@example.com`
}

/** Entra pela tela de login com e-mail e senha. Nenhum spec o usa hoje. */
export async function signIn(page: Page, email: string, password: string) {
  await page.goto("/sign-in")
  await page.getByLabel(pt.signIn.email).fill(email)
  await page.getByLabel(pt.signIn.password).fill(password)
  await page.getByRole("button", { name: pt.signIn.submit }).click()
}

/**
 * Entra com o admin de `credentials.ts` e espera chegar a `returnTo`. Se a
 * entrada passa por `/legal/accept`, aceita os Termos antes.
 */
export async function signInAsAdmin(page: Page, returnTo = "/admin/privacy") {
  await page.goto(`/sign-in?returnTo=${encodeURIComponent(returnTo)}`)
  await page.getByLabel(pt.signIn.email).fill(e2eAdmin.email)
  await page.getByLabel(pt.signIn.password).fill(e2eAdmin.password)
  await page.getByRole("button", { name: pt.signIn.submit }).click()
  // O admin criado pelo script entra a primeira vez pelo novo aceite dos Termos (SDD 13.3).
  await page.waitForURL((url) => url.pathname === "/legal/accept" || url.pathname === returnTo)
  if (new URL(page.url()).pathname === "/legal/accept") {
    await page.getByRole("button", { name: pt.legalAccept.accept }).click()
  }
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
