import { expect, test } from "@playwright/test"

import { pt } from "../src/i18n/pt.ts"

import { expectNoSeriousViolations } from "./api.ts"
import { installAccountApi, type AccountApi } from "./account-api.ts"

let api: AccountApi

test.beforeEach(async ({ page }) => {
  api = await installAccountApi(page)
})

test("J5 o membro corrige o perfil, exporta os dados e exclui a conta", async ({
  page,
}) => {
  await page.goto("/account")
  await expect(
    page.getByRole("heading", { name: pt.pages.account })
  ).toBeVisible()
  await expectNoSeriousViolations(page)

  const name = page.getByLabel(pt.account.profile.fullName)
  await name.fill("Maria Nova")
  await page.getByRole("button", { name: pt.account.profile.save }).click()
  await expect(page.getByText(pt.account.profile.saved)).toBeVisible()
  expect(api.member().full_name).toBe("Maria Nova")

  await page.getByRole("tab", { name: pt.account.tabs.conversations }).click()
  await expect(page.getByText("Qual é o horário de visita?")).toBeVisible()

  await page.getByRole("tab", { name: pt.account.tabs.privacy }).click()
  await expectNoSeriousViolations(page)
  const personalization = page.getByRole("switch", {
    name: pt.account.privacy.personalization,
  })
  await personalization.click()
  await expect(personalization).toBeChecked()
  await personalization.click()
  await expect(personalization).not.toBeChecked()

  const download = page.waitForEvent("download")
  await page
    .getByRole("button", { name: pt.account.privacy.exportButton })
    .click()
  expect((await download).suggestedFilename()).toBe("atrium-meus-dados.json")
  expect(api.exported()).toBe(true)

  await page
    .getByRole("button", { name: pt.account.privacy.deleteButton })
    .click()
  const dialog = page.getByRole("alertdialog")
  await expect(dialog).toBeVisible()
  await expectNoSeriousViolations(page)
  const confirm = dialog.getByRole("button", {
    name: pt.account.privacy.deleteConfirm,
  })
  await expect(confirm).toBeDisabled()
  await dialog
    .getByLabel(pt.account.privacy.deleteConfirmLabel)
    .fill(pt.account.privacy.deleteConfirmWord)
  await confirm.click()
  await expect(
    page.getByRole("heading", { name: pt.home.title })
  ).toBeVisible()
  expect(api.deleted()).toBe(true)

  await page.goto("/account")
  await expect(
    page.getByRole("heading", { name: pt.pages.signIn })
  ).toBeVisible()
})

test("J5 funciona no celular com movimento reduzido", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto("/account")
  await page.getByRole("tab", { name: pt.account.tabs.privacy }).click()
  await expect(
    page.getByRole("button", { name: pt.account.privacy.deleteButton })
  ).toBeVisible()
  await expectNoSeriousViolations(page)
})
