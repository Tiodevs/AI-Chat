/**
 * J1 a J5 só com teclado: Tab, Enter, Espaço e setas. Etapa 9.1, CA-2,
 * NFR-14 e seção 15.8 do SDD.
 *
 * Suíte ao vivo, só no projeto `live-desktop` (Desktop Chrome sem redução de
 * movimento), contra a API de verdade. Nenhum clique de mouse depois de a
 * página abrir, salvo a criação da conta de apoio da J5 pelo
 * `registerByForm`. O foco anda com o `tabTo` de `a11y.ts`.
 */
import type { Locator, Page } from "@playwright/test"

import { pt } from "../../src/i18n/pt.ts"
import { visitingQuestion } from "../api.ts"

import { tabTo } from "./a11y.ts"
import { expect, registerByForm, test, uniqueEmail } from "./fixtures.ts"

/** Leva o foco ao alvo com Tab e aperta a tecla, Enter por padrão. */
async function press(page: Page, target: Locator, key = "Enter") {
  await tabTo(page, target)
  await page.keyboard.press(key)
}

/** Leva o foco ao campo com Tab e digita o texto. */
async function typeInto(page: Page, target: Locator, text: string) {
  await tabTo(page, target)
  await page.keyboard.type(text)
}

test("J1 pelo teclado: sugestão, resposta e fontes", async ({ page }) => {
  await page.goto("/")
  await press(page, page.getByRole("radio", { name: visitingQuestion().label }))
  await expect(page).toHaveURL(/\/ask\//)
  await expect(page.locator("ol").getByText(/11:00–20:00/)).toBeVisible()
  await press(page, page.getByRole("button", { name: pt.ask.showSources }))
  await expect(page.locator("ol").getByText("1. Visitas")).toBeVisible()
})

test("J2 pelo teclado: Enter envia e a recusa aparece", async ({ page }) => {
  await page.goto("/")
  await typeInto(page, page.getByLabel(pt.ask.questionLabel), "Que remédio tomo para dor de cabeça?")
  await page.keyboard.press("Enter")
  await expect(page.locator("ol").getByText(pt.ask.privacyNote)).toBeVisible()
})

test("J3 pelo teclado: cadastro por conversa até a conta", async ({ page }) => {
  const email = uniqueEmail("teclado-j3")
  await page.goto("/register")
  const message = page.getByLabel(pt.registration.messageLabel)
  await typeInto(page, message, "Elisa Prado")
  await page.keyboard.press("Enter")
  await expect(page.getByText("Elisa Prado").first()).toBeVisible()
  await expect(message).toBeEnabled()
  // O campo fica `disabled` durante o turno, e o navegador tira o foco dele.
  // O `focus()` devolve o foco sem clique, mas não é uma tecla.
  await message.focus()
  await page.keyboard.type(email)
  await page.keyboard.press("Enter")
  for (let step = 0; step < 3; step += 1) {
    const skip = page.getByRole("button", { name: pt.registration.skip })
    await expect(skip).toBeEnabled()
    await press(page, skip)
  }
  const password = page.getByRole("textbox", { name: pt.registration.fields.password, exact: true })
  // O PasswordCard leva o foco ao campo sozinho (M12).
  await expect(password).toBeFocused()
  await page.keyboard.type("senha-segura-1")
  await page.keyboard.press("Enter")
  await press(page, page.getByRole("button", { name: pt.registration.confirm }))
  await press(page, page.getByRole("checkbox", { name: pt.registration.terms }), "Space")
  await press(page, page.getByRole("checkbox", { name: pt.registration.age }), "Space")
  await press(page, page.getByRole("button", { name: pt.registration.createAccount }))
  await expect(page.getByRole("heading", { name: pt.pages.account })).toBeVisible()
})

test("J4 pelo teclado: do chat ao formulário sem perder o nome", async ({ page }) => {
  await page.goto("/register")
  await typeInto(page, page.getByLabel(pt.registration.messageLabel), "Fábio Reis")
  await page.keyboard.press("Enter")
  await expect(page.getByText("Fábio Reis").first()).toBeVisible()
  await press(page, page.getByRole("link", { name: pt.registration.useForm }))
  await expect(page.getByLabel(pt.registration.fields.full_name)).toHaveValue("Fábio Reis")
  await typeInto(page, page.getByLabel(pt.registration.fields.email), uniqueEmail("teclado-j4"))
  await typeInto(
    page,
    page.getByRole("textbox", { name: pt.registration.fields.password, exact: true }),
    "senha-segura-1",
  )
  await press(page, page.getByRole("checkbox", { name: pt.registration.terms }), "Space")
  await press(page, page.getByRole("checkbox", { name: pt.registration.age }), "Space")
  await press(page, page.getByRole("button", { name: pt.registration.createAccount }))
  await expect(page.getByRole("heading", { name: pt.pages.account })).toBeVisible()
})

test("J5 pelo teclado: abas, exportação e exclusão", async ({ page }) => {
  await registerByForm(page, uniqueEmail("teclado-j5"), "Gabi Nunes")
  // As abas seguem o padrão do Radix: Tab chega à aba ativa e as setas trocam de aba. O
  // Radix move o foco logo depois da tecla, então cada passo espera a aba chegar.
  await tabTo(page, page.getByRole("tab", { name: pt.account.tabs.profile }))
  for (const name of [pt.account.tabs.conversations, pt.account.tabs.privacy]) {
    await page.keyboard.press("ArrowRight")
    await expect(page.getByRole("tab", { name })).toBeFocused()
  }
  await expect(page.getByRole("tab", { name: pt.account.tabs.privacy })).toHaveAttribute(
    "aria-selected",
    "true",
  )
  const download = page.waitForEvent("download")
  await press(page, page.getByRole("button", { name: pt.account.privacy.exportButton }))
  expect((await download).suggestedFilename()).toBe("atrium-meus-dados.json")

  await press(page, page.getByRole("button", { name: pt.account.privacy.deleteButton }))
  const dialog = page.getByRole("alertdialog")
  await expect(dialog).toBeVisible()
  await typeInto(
    page,
    dialog.getByLabel(pt.account.privacy.deleteConfirmLabel),
    pt.account.privacy.deleteConfirmWord,
  )
  await press(page, dialog.getByRole("button", { name: pt.account.privacy.deleteConfirm }))
  await expect(page.getByRole("heading", { name: pt.home.title })).toBeVisible()
})
