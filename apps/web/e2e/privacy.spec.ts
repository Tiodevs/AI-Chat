import { expect, test } from "@playwright/test"

import { pt } from "../src/i18n/pt.ts"

import { expectNoSeriousViolations } from "./api.ts"

const due = "2026-11-18T12:00:00.000Z"

test.beforeEach(async ({ page }) => {
  await page.route("**/backend/v1/**", async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (request.method() === "GET" && path.endsWith("/v1/legal/versions")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          terms: "2026-10-25.1",
          privacy_notice: "2026-10-25.1",
          privacy_contact_email: "privacidade@harborlight.example",
        }),
      })
      return
    }
    if (request.method() === "POST" && path.endsWith("/v1/privacy/requests")) {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: "00000000-0000-4000-8000-0000000000e1",
          request_type: "deletion",
          status: "open",
          received_at: "2026-11-03T12:00:00.000Z",
          due_at: due,
        }),
      })
      return
    }
    await route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "unauthenticated",
          message: "Entre para continuar.",
          request_id: "01E2E",
        },
      }),
    })
  })
})

test("J8 uma pessoa sem conta pede a eliminação pelo canal", async ({ page }) => {
  await page.goto("/privacy#pedidos")
  await expect(
    page.getByRole("heading", { level: 1, name: pt.pages.privacy })
  ).toBeVisible()
  await expectNoSeriousViolations(page)

  await page.getByLabel(pt.privacyRequest.email).fill("visitante@example.com")
  await page
    .getByRole("radio", { name: pt.privacyRequest.types.deletion })
    .click()
  await page
    .getByLabel(pt.privacyRequest.description)
    .fill("Quero que apaguem a minha conversa de convidado.")
  const sent = page.waitForRequest(
    (request) =>
      request.method() === "POST" &&
      request.url().endsWith("/backend/v1/privacy/requests")
  )
  await page.getByRole("button", { name: pt.privacyRequest.submit }).click()
  expect((await sent).postDataJSON()).toMatchObject({
    contact_email: "visitante@example.com",
    request_type: "deletion",
  })
  await expect(page.getByRole("status")).toContainText(
    pt.privacyRequest.sent.split("{date}")[0]
  )
  await expectNoSeriousViolations(page)
})

test("os Termos abrem com a versão vigente", async ({ page }) => {
  await page.goto("/terms")
  await expect(
    page.getByRole("heading", { level: 1, name: pt.pages.terms })
  ).toBeVisible()
  await expect(page.getByText("Versão 2026-10-25.1")).toBeVisible()
  await expectNoSeriousViolations(page)
})
