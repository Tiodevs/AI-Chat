/**
 * J3 e J4 com a API simulada: o cadastro pela conversa com os opcionais
 * pulados e a troca para o formulário com os campos já entendidos. FR-5,
 * FR-6 e NFR-14, seções 7.2, 15.3 e 15.8 do SDD.
 *
 * Suíte simulada, projeto `mobile` (Pixel 5 com movimento reduzido). O
 * `beforeEach` instala o `installRegistrationApi`, e a J3 usa o
 * `registerByChat`, os dois de `registration-api.ts`. Sem API e sem banco.
 */
import { expect, test } from "@playwright/test"

import { pt } from "../src/i18n/pt.ts"

import { expectNoSeriousViolations } from "./api.ts"
import { installRegistrationApi, registerByChat } from "./registration-api.ts"

test.beforeEach(async ({ page }) => {
  await installRegistrationApi(page)
})

test("J3 cria a conta pulando os opcionais", async ({ page }) => {
  await page.goto("/register")
  await expect(page.getByLabel(pt.registration.messageLabel)).toBeVisible()
  await expect(
    page.getByRole("link", { name: pt.registration.useForm })
  ).toBeVisible()
  await expectNoSeriousViolations(page)
  await registerByChat(page)
  await expectNoSeriousViolations(page)
})

test("J4 leva os campos do chat para o formulário", async ({ page }) => {
  await page.goto("/register")
  await page.getByLabel(pt.registration.messageLabel).fill("Ana Costa")
  await page.getByRole("button", { name: pt.registration.send }).click()
  await expect(page.getByText("Ana Costa").first()).toBeVisible()
  await page.getByRole("link", { name: pt.registration.useForm }).click()
  // FR-6: o nome entendido vem preenchido, a senha nunca, e a personalização
  // começa desligada.
  await expect(page.getByLabel(pt.registration.fields.full_name)).toHaveValue(
    "Ana Costa"
  )
  await expect(
    page.getByRole("textbox", {
      name: pt.registration.fields.password,
      exact: true,
    }),
  ).toHaveValue("")
  await expect(
    page.getByRole("checkbox", { name: pt.registration.personalization })
  ).not.toBeChecked()
  await expectNoSeriousViolations(page)

  await page
    .getByLabel(pt.registration.fields.email)
    .fill("ana.form@example.com")
  await page
    .getByRole("textbox", {
      name: pt.registration.fields.password,
      exact: true,
    })
    .fill("senha-segura-1")
  await page.getByRole("checkbox", { name: pt.registration.terms }).check()
  await page.getByRole("checkbox", { name: pt.registration.age }).check()
  await page
    .getByRole("button", { name: pt.registration.createAccount })
    .click()
  await expect(
    page.getByRole("heading", { name: pt.pages.account })
  ).toBeVisible()
  await expectNoSeriousViolations(page)
})
