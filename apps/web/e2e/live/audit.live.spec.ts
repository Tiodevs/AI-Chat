/**
 * Auditoria de acessibilidade de todas as telas e diálogos. Etapa 9.1, CA-1
 * e CA-2, NFR-14 e seção 15.8 do SDD.
 *
 * Suíte ao vivo, nos projetos `live` (Pixel 5 com movimento reduzido) e
 * `live-desktop` (Desktop Chrome sem redução). São três testes, para as telas
 * públicas, as do membro e as do admin, e cada um cria na API de verdade os
 * dados de que precisa.
 */
import AxeBuilder from "@axe-core/playwright"
import type { Page } from "@playwright/test"

import { pt } from "../../src/i18n/pt.ts"
import { visitingQuestion } from "../api.ts"

import { smallTargets } from "./a11y.ts"
import { expect, registerByForm, signInAsAdmin, test, uniqueEmail } from "./fixtures.ts"

/**
 * Audita a tela ou o diálogo aberto: espera a rede parar, roda o axe sem
 * aceitar violação séria ou crítica e mede os alvos de toque, de 44 px no
 * celular e 24 px no desktop. Usa `expect.soft`: as falhas se acumulam, e um
 * teste mostra todas.
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

/** Fecha o diálogo aberto com Esc e confere que nenhum diálogo ficou. */
async function closeDialog(page: Page) {
  await page.keyboard.press("Escape")
  await expect(page.getByRole("dialog")).toHaveCount(0)
  await expect(page.getByRole("alertdialog")).toHaveCount(0)
}

/**
 * Abaixo de 768 px, abre o menu que estiver à vista, o da barra lateral ou o
 * do visitante, e devolve `true`. No desktop, a barra já está na tela, e a
 * função devolve `false`.
 */
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

  // O roteador não tem rota `*` nem `ErrorBoundary` na raiz, então este
  // endereço mostra a tela de erro padrão do React Router, não uma página em
  // português (seção 13.3). A Etapa 14.1 cria a página não encontrada.
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
  // Um membro numa rota de admin vê a página 403 (seção 13.3).
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
  } else {
    // Entre 768 e 1023 px a barra já começa recolhida, e os controles só com ícone precisam
    // continuar com nome para o leitor de tela.
    await page.getByRole("button", { name: pt.sidebar.collapse }).click()
    await expect(page.getByRole("button", { name: pt.sidebar.expand })).toBeVisible()
    await audit(page, "barra lateral recolhida")
    await page.getByRole("button", { name: pt.sidebar.expand }).click()
  }
})
