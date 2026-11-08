/**
 * J1, J2, J3, J4, J5 e J8 da seção 15.3 contra a API de verdade. FR-1 a
 * FR-3, FR-5, FR-6, FR-9, FR-16, FR-17 e NFR-14, seção 21.1 do SDD e
 * ADR-014.
 *
 * Suíte ao vivo, projeto `live` (Pixel 5 com movimento reduzido). A API roda
 * com o adaptador `demo` e o corpus semeado, sobre o PostgreSQL da e2e: as
 * respostas saem das regras do `demo` e do texto de `content/corpus`. Cada
 * teste ganha as fixtures automáticas de `fixtures.ts` (IP próprio e checagem
 * de CSP) e cria as contas com e-mail único.
 */
import { pt } from "../../src/i18n/pt.ts"
import { visitingQuestion } from "../api.ts"

import {
  expect,
  expectNoSeriousViolations,
  registerByForm,
  signInAsAdmin,
  test,
  uniqueEmail,
} from "./fixtures.ts"

test("J1 o convidado pergunta o horário de visita e recebe a resposta com fonte", async ({
  page,
}) => {
  await page.goto("/")
  await expect(page.getByRole("heading", { name: pt.home.title })).toBeVisible()
  await expectNoSeriousViolations(page)

  await page.getByRole("radio", { name: visitingQuestion().label }).click()
  await expect(page).toHaveURL(/\/ask\//)
  // O `demo` responde com a primeira frase do bloco mais bem colocado, e o
  // horário vem de `content/corpus/02-visiting.md`.
  const thread = page.locator("ol")
  await expect(thread.getByText(/11:00–20:00/)).toBeVisible()
  await page.getByRole("button", { name: pt.ask.showSources }).click()
  await expect(thread.getByText("1. Visitas")).toBeVisible()
  await expect(page.getByRole("button", { name: pt.ask.useful, exact: true })).toBeVisible()
  await expectNoSeriousViolations(page)

  // A conversa vem do banco ao recarregar, com a mesma resposta.
  await page.reload()
  await expect(page.locator("ol").getByText(/11:00–20:00/)).toBeVisible()
})

test("J2 o convidado descreve um sintoma e a mensagem não fica guardada", async ({ page }) => {
  const question = "Estou com dor no peito. Que remédio devo tomar?"
  await page.goto("/")
  await page.getByLabel(pt.ask.questionLabel).fill(question)
  await page.getByRole("button", { name: pt.ask.send }).click()
  const thread = page.locator("ol")
  await expect(
    thread.getByText("Não posso ajudar com sintomas, diagnóstico ou medicamento.", {
      exact: false,
    }),
  ).toBeVisible()
  await expect(thread.getByText(pt.ask.privacyNote)).toBeVisible()
  // Recarregar mostra o que o banco guardou: o marcador no lugar da pergunta,
  // que a tela exibe como o aviso de privacidade (FR-17).
  await page.reload()
  await expect(page.locator("ol").getByText(pt.ask.privacyNote)).toBeVisible()
  await expect(page.locator("ol").getByText(question)).toHaveCount(0)
  await expectNoSeriousViolations(page)
})

test("J3 cria a conta pela conversa pulando os opcionais", async ({ page }) => {
  const email = uniqueEmail("j3")
  await page.goto("/register")
  const message = page.getByLabel(pt.registration.messageLabel)
  await expect(message).toBeVisible()
  await expectNoSeriousViolations(page)

  await message.fill("Ana Costa")
  await page.getByRole("button", { name: pt.registration.send }).click()
  await expect(page.getByText("Ana Costa").first()).toBeVisible()
  await message.fill(email)
  await page.getByRole("button", { name: pt.registration.send }).click()
  for (let step = 0; step < 3; step += 1) {
    await page.getByRole("button", { name: pt.registration.skip }).click()
  }
  const password = page.getByRole("textbox", { name: pt.registration.fields.password, exact: true })
  await expect(password).toBeFocused()
  await password.fill("senha-segura-1")
  await page.getByRole("button", { name: pt.registration.send }).click()
  await expect(page.getByText(email).first()).toBeVisible()
  await page.getByRole("button", { name: pt.registration.confirm }).click()
  await page.getByRole("checkbox", { name: pt.registration.terms }).check()
  await page.getByRole("checkbox", { name: pt.registration.age }).check()
  await expectNoSeriousViolations(page)
  await page.getByRole("button", { name: pt.registration.createAccount }).click()
  await expect(page.getByRole("heading", { name: pt.pages.account })).toBeVisible()
  await expect(page.getByLabel(pt.account.profile.email)).toHaveValue(email)
})

test("J4 troca para o formulário no meio da conversa sem perder o nome", async ({ page }) => {
  await page.goto("/register")
  await page.getByLabel(pt.registration.messageLabel).fill("Bruno Lima")
  await page.getByRole("button", { name: pt.registration.send }).click()
  await expect(page.getByText("Bruno Lima").first()).toBeVisible()
  // Clicar com a resposta ainda a caminho: o link espera o turno e leva o nome entendido.
  await page.getByRole("link", { name: pt.registration.useForm }).click()
  await expect(page.getByLabel(pt.registration.fields.full_name)).toHaveValue("Bruno Lima")
  await expect(
    page.getByRole("textbox", { name: pt.registration.fields.password, exact: true }),
  ).toHaveValue("")
  await expectNoSeriousViolations(page)

  await page.getByLabel(pt.registration.fields.email).fill(uniqueEmail("j4"))
  await page
    .getByRole("textbox", { name: pt.registration.fields.password, exact: true })
    .fill("senha-segura-1")
  await page.getByRole("checkbox", { name: pt.registration.terms }).check()
  await page.getByRole("checkbox", { name: pt.registration.age }).check()
  await page.getByRole("button", { name: pt.registration.createAccount }).click()
  await expect(page.getByRole("heading", { name: pt.pages.account })).toBeVisible()
})

test("J5 o membro exporta os dados e exclui a conta", async ({ page }) => {
  await registerByForm(page, uniqueEmail("j5"), "Carla Dias")
  await page.getByRole("tab", { name: pt.account.tabs.privacy }).click()
  await expectNoSeriousViolations(page)

  const download = page.waitForEvent("download")
  await page.getByRole("button", { name: pt.account.privacy.exportButton }).click()
  const file = await download
  expect(file.suggestedFilename()).toBe("atrium-meus-dados.json")

  await page.getByRole("button", { name: pt.account.privacy.deleteButton }).click()
  const dialog = page.getByRole("alertdialog")
  await expect(dialog).toBeVisible()
  await dialog
    .getByLabel(pt.account.privacy.deleteConfirmLabel)
    .fill(pt.account.privacy.deleteConfirmWord)
  await dialog.getByRole("button", { name: pt.account.privacy.deleteConfirm }).click()
  await expect(page.getByRole("heading", { name: pt.home.title })).toBeVisible()

  await page.goto("/account")
  await expect(page.getByRole("heading", { name: pt.pages.signIn })).toBeVisible()
})

test("J8 a pessoa sem conta pede a eliminação e o admin conclui o pedido", async ({ page }) => {
  const contact = uniqueEmail("j8")
  await page.goto("/privacy#pedidos")
  await page.getByLabel(pt.privacyRequest.email).fill(contact)
  await page.getByRole("radio", { name: pt.privacyRequest.types.deletion }).click()
  await page
    .getByLabel(pt.privacyRequest.description)
    .fill("Quero que apaguem a minha conversa de convidado.")
  await page.getByRole("button", { name: pt.privacyRequest.submit }).click()
  await expect(page.getByRole("status")).toContainText(pt.privacyRequest.sent.split("{date}")[0] ?? "")

  await signInAsAdmin(page, "/admin/privacy")
  await expect(page.getByRole("heading", { level: 1, name: pt.pages.privacyRequests })).toBeVisible()
  const open = page.getByRole("button", {
    name: `${pt.privacyQueue.table.open}: ${pt.privacyRequest.types.deletion}, ${contact}`,
  })
  await expect(open).toBeVisible()
  // Recebido agora, vence em 15 dias corridos: o badge conta dias inteiros que faltam.
  const row = page.getByRole("row").filter({ hasText: contact })
  await expect(row.getByText(/Vence em 1[45] dias/)).toBeVisible()
  await expectNoSeriousViolations(page)

  await open.click()
  const sheet = page.getByRole("dialog")
  await sheet.getByRole("radio", { name: pt.privacyQueue.status.in_progress }).click()
  await sheet.getByRole("button", { name: pt.privacyQueue.detail.save }).click()
  await expect(sheet.getByRole("status")).toContainText(pt.privacyQueue.status.in_progress)
  await sheet.getByRole("radio", { name: pt.privacyQueue.status.done }).click()
  await sheet
    .getByLabel(pt.privacyQueue.detail.note)
    .fill("Conversa de convidado apagada e titular avisado por e-mail.")
  await sheet.getByRole("button", { name: pt.privacyQueue.detail.save }).click()
  await expect(sheet.getByText(pt.privacyQueue.detail.closedNotice)).toBeVisible()
  await expectNoSeriousViolations(page)
})
