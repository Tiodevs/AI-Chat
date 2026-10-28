import { expect, test } from "@playwright/test"

import { pt } from "../src/i18n/pt.ts"

import { installConversationApi, visitingQuestion } from "./api.ts"
import { installRegistrationApi, registerByChat } from "./registration-api.ts"

test("J1 com movimento ligado não quebra a animação", async ({ page }) => {
  const errors: string[] = []
  page.on("pageerror", (error) => {
    errors.push(error.message)
  })
  await installConversationApi(page)
  await page.goto("/")
  await page.getByRole("radio", { name: visitingQuestion().label }).click()
  await expect(page.locator("ol").getByText("11:00")).toBeVisible()
  await expect(
    page.getByRole("button", { name: pt.ask.useful, exact: true })
  ).toBeVisible()
  expect(errors).toEqual([])
})

test("J3 com movimento ligado chega à senha e cria a conta", async ({
  page,
}) => {
  const errors: string[] = []
  page.on("pageerror", (error) => {
    errors.push(error.message)
  })
  await installRegistrationApi(page)
  await registerByChat(page)
  expect(errors).toEqual([])
})
