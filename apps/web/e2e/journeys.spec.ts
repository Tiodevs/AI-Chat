/**
 * J1 e J2 na tela, com a API simulada, e o axe em `/ask`. FR-1, FR-3 e
 * NFR-14, seções 15.3 e 15.8 do SDD.
 *
 * Suíte simulada, projeto `mobile` (Pixel 5 com movimento reduzido). O
 * `beforeEach` instala o `installConversationApi` de `api.ts`, então nenhum
 * pedido chega à API nem ao banco.
 */
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

  // A recarga remonta a conversa pelo `GET /v1/conversations/{id}`, que o
  // falso devolve já com a resposta e a citação.
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
  // A prova aqui é da tela: ela troca a pergunta pelo aviso de privacidade
  // quando a resposta termina em `refused`. O que o banco guarda (FR-17) é
  // conferido em `live/journeys.live.spec.ts`, depois de recarregar.
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
