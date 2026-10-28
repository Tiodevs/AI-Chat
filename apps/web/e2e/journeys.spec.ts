import { expect, test } from "@playwright/test"

import { pt } from "../src/i18n/pt.ts"

import {
  expectNoSeriousViolations,
  installConversationApi,
  visitingQuestion,
} from "./api.ts"

test.beforeEach(async ({ page }) => {
  await installConversationApi(page)
})

test("J1 responde o horário de visita no celular, com fonte e sem cadastro", async ({
  page,
}) => {
  await page.goto("/")
  await expect(
    page.getByRole("heading", { name: pt.home.title }),
  ).toBeVisible()
  await expectNoSeriousViolations(page)

  await page.getByRole("radio", { name: visitingQuestion().label }).click()
  await expect(page).toHaveURL(new RegExp(`/ask/`))
  const thread = page.locator("ol")
  await expect(thread.getByText("11:00")).toBeVisible()
  await page.getByRole("button", { name: pt.ask.showSources }).click()
  await expect(thread.getByText("Visitas")).toBeVisible()
  await expect(
    page.getByRole("button", { name: pt.ask.useful, exact: true }),
  ).toBeVisible()
  await expect(page.getByRole("button", { name: pt.ask.copy })).toBeVisible()
  expect(page.url()).not.toContain("/register")
  expect(page.url()).not.toContain("/sign-in")
  await expectNoSeriousViolations(page)

  await page.reload()
  await expect(page.locator("ol").getByText("11:00")).toBeVisible()
  await expect(
    page.getByRole("button", { name: pt.ask.useful, exact: true }),
  ).toBeVisible()
})

test("J2 recusa orientação médica e avisa que a mensagem não fica guardada", async ({
  page,
}) => {
  const question = "Que remédio tomo para dor de cabeça?"
  await page.goto("/")
  await page.getByLabel(pt.ask.questionLabel).fill(question)
  await page.getByRole("button", { name: pt.ask.send }).click()
  const thread = page.locator("ol")
  await expect(thread.getByText(pt.ask.privacyNote)).toBeVisible()
  await expect(
    thread.getByText("Não posso ajudar com sintomas, diagnóstico ou medicamento."),
  ).toBeVisible()
  await expect(thread.getByText(question)).toHaveCount(0)
  await expect(page).toHaveURL(new RegExp(`/ask/`))
})

test("axe não encontra violação séria em /ask", async ({ page }) => {
  await page.goto("/ask")
  await expect(page.getByRole("heading", { name: pt.pages.ask })).toBeVisible()
  await expectNoSeriousViolations(page)
})
