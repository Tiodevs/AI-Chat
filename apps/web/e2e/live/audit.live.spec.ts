import AxeBuilder from "@axe-core/playwright"
import type { Page } from "@playwright/test"

import { pt } from "../../src/i18n/pt.ts"
import { visitingQuestion } from "../api.ts"

import { smallTargets } from "./a11y.ts"
import { expect, registerByForm, signInAsAdmin, test, uniqueEmail } from "./fixtures.ts"

/**
 * Auditoria de acessibilidade de todas as telas. Etapa 9.1, CA-1 e CA-2 (SDD 15.8).
 *
 * Em cada tela e em cada diálogo aberto: axe sem violação séria ou crítica e alvos de toque de
 * 44 px no celular e 24 px no desktop. As falhas são acumuladas, para um teste mostrar todas.
 */
async function audit(page: Page, where: string) {
  await page.waitForLoadState("networkidle")
  const results = await new AxeBuilder({ page }).analyze()
  const serious = results.violations
    .filter((violation) => violation.impact === "serious" || violation.impact === "critical")
    .map((violation) => `${violation.id}: ${violation.nodes.map((node) => node.target.join(" ")).join(" | ")}`)
  expect.soft(serious, `axe em ${where}`).toEqual([])
  const width = page.viewportSize()?.width ?? 1280
  const minimum = width < 768 ? 44 : 24
  expect.soft(await smallTargets(page, minimum), `alvos de ${String(minimum)} px em ${where}`).toEqual([])
}

async function closeDialog(page: Page) {
  await page.keyboard.press("Escape")
  await expect(page.getByRole("dialog")).toHaveCount(0)
  await expect(page.getByRole("alertdialog")).toHaveCount(0)
}

async function openNavigation(page: Page) {
  const width = page.viewportSize()?.width ?? 1280
  if (width >= 768) {
    return false
  }
  const menu = page.getByRole("button", { name: pt.sidebar.openMenu })
  const guest = page.getByRole("button", { name: pt.sidebar.guestMenu })
  if (await menu.isVisible()) {
    await menu.click()
    return true
  }
  if (await guest.isVisible()) {
    await guest.click()
    return true
  }
  return false
}

test("telas públicas e a conversa", async ({ page }) => {
  for (const [path, heading] of [
    ["/", pt.home.title],
    ["/ask", pt.pages.ask],
    ["/register", pt.pages.register],
    ["/register/form", pt.pages.registerForm],
    ["/sign-in", pt.pages.signIn],
    ["/privacy", pt.pages.privacy],
    ["/terms", pt.pages.terms],
  ] as const) {
    await page.goto(path)
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible()
    await audit(page, path)
  }

  await page.goto("/nao-existe")
  await audit(page, "página não encontrada")

  await page.goto("/")
  await page.getByRole("radio", { name: visitingQuestion().label }).click()
  await expect(page.locator("ol").getByText(/11:00–20:00/)).toBeVisible()
  await page.getByRole("button", { name: pt.ask.showSources }).click()
  await audit(page, "/ask/:id com resposta e fontes")

  if (await openNavigation(page)) {
    await audit(page, "menu do visitante")
    await closeDialog(page)
  }
  await page.keyboard.press("Control+k")
  await expect(page.getByRole("dialog")).toBeVisible()
  await audit(page, "paleta de comandos")
  await closeDialog(page)
})

test("telas do membro", async ({ page }) => {
  await registerByForm(page, uniqueEmail("auditoria"), "Diego Alves")
  await audit(page, "/account, Perfil")
  await page.getByRole("tab", { name: pt.account.tabs.conversations }).click()
  await audit(page, "/account, Conversas")
  await page.getByRole("tab", { name: pt.account.tabs.privacy }).click()
  await audit(page, "/account, Privacidade")
  await page.getByRole("button", { name: pt.account.privacy.deleteButton }).click()
  await expect(page.getByRole("alertdialog")).toBeVisible()
  await audit(page, "diálogo de exclusão da conta")
  await closeDialog(page)

  if (await openNavigation(page)) {
    await audit(page, "menu do membro")
    await closeDialog(page)
  }
  await page.goto("/admin")
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible()
  await audit(page, "admin para membro (403)")
})

test("telas do admin", async ({ page }) => {
  // Dados para as telas: uma conversa de convidado e um pedido de titular.
  await page.goto("/")
  await page.getByRole("radio", { name: visitingQuestion().label }).click()
  await expect(page.locator("ol").getByText(/11:00–20:00/)).toBeVisible()
  await page.goto("/privacy#pedidos")
  await page.getByLabel(pt.privacyRequest.email).fill(uniqueEmail("auditoria-dsr"))
  await page.getByRole("radio", { name: pt.privacyRequest.types.access }).click()
  await page.getByLabel(pt.privacyRequest.description).fill("Quero uma cópia dos meus dados.")
  await page.getByRole("button", { name: pt.privacyRequest.submit }).click()
  await expect(page.getByRole("status")).toBeVisible()

  await signInAsAdmin(page, "/admin")
  await expect(page.getByRole("heading", { level: 1, name: pt.pages.admin })).toBeVisible()
  await audit(page, "/admin")

  await page.goto("/admin/documents")
  await expect(page.getByRole("heading", { level: 1, name: pt.pages.documents })).toBeVisible()
  await audit(page, "/admin/documents")
  await page.getByRole("button", { name: new RegExp(`^${pt.documents.actions.replace}:`) }).first().click()
  await expect(page.getByRole("dialog")).toBeVisible()
  await audit(page, "sheet de substituir documento")
  await closeDialog(page)
  await page.getByRole("button", { name: new RegExp(`^${pt.documents.actions.archive}:`) }).first().click()
  await expect(page.getByRole("alertdialog")).toBeVisible()
  await audit(page, "diálogo de arquivar documento")
  await closeDialog(page)

  await page.goto("/admin/quality")
  await expect(page.getByRole("heading", { level: 1, name: pt.pages.quality })).toBeVisible()
  await audit(page, "/admin/quality")
  await page.getByRole("button", { name: new RegExp(`^${pt.quality.table.open}:`) }).first().click()
  await expect(page.getByRole("dialog")).toBeVisible()
  await audit(page, "inspetor de conversa")
  await closeDialog(page)

  await page.goto("/admin/privacy")
  await expect(page.getByRole("heading", { level: 1, name: pt.pages.privacyRequests })).toBeVisible()
  await audit(page, "/admin/privacy")
  await page.getByRole("button", { name: new RegExp(`^${pt.privacyQueue.table.open}:`) }).first().click()
  await expect(page.getByRole("dialog")).toBeVisible()
  await audit(page, "detalhe do pedido de titular")
  await closeDialog(page)

  if (await openNavigation(page)) {
    await audit(page, "menu do admin")
    await closeDialog(page)
  }
})
