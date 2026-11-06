import { expect, test, type Route } from "@playwright/test"

import { pt } from "../src/i18n/pt.ts"

import { expectNoSeriousViolations } from "./api.ts"

const t = pt.privacyQueue
const d = pt.privacyQueue.detail
const now = "2031-01-15T12:00:00.000Z"

type Item = {
  id: string
  request_type: string
  status: string
  contact_email: string
  description: string
  received_at: string
  due_at: string
  closed_at: string | null
  resolution_note: string | null
  overdue: boolean
  linked_account: boolean
}

const admin = {
  id: "00000000-0000-4000-8000-0000000000ad",
  email: "admin@example.com",
  full_name: "Ana Operadora",
  phone: null,
  visitor_type: null,
  visit_reason: null,
  role: "admin",
  needs_legal_acceptance: false,
}

function queue(): Item[] {
  return [
    {
      id: "00000000-0000-4000-8000-000000000e1",
      request_type: "deletion",
      status: "open",
      contact_email: "visitante@example.com",
      description: "Quero que apaguem a minha conversa de convidado.",
      received_at: "2030-12-26T12:00:00.000Z",
      due_at: "2031-01-10T12:00:00.000Z",
      closed_at: null,
      resolution_note: null,
      overdue: true,
      linked_account: false,
    },
    {
      id: "00000000-0000-4000-8000-000000000e2",
      request_type: "access",
      status: "open",
      contact_email: "membro@example.com",
      description: "Quero uma cópia dos meus dados.",
      received_at: "2031-01-12T12:00:00.000Z",
      due_at: "2031-01-27T12:00:00.000Z",
      closed_at: null,
      resolution_note: null,
      overdue: false,
      linked_account: true,
    },
  ]
}

async function fulfill(route: Route, status: number, body: unknown) {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) })
}

test("J8 o admin vê o pedido atrasado primeiro e o conclui com nota", async ({ page }) => {
  const items = queue()
  const patches: unknown[] = []
  await page.route("**/backend/v1/**", async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (request.method() === "GET" && path.endsWith("/v1/me")) {
      await fulfill(route, 200, admin)
      return
    }
    if (request.method() === "GET" && path.endsWith("/v1/admin/privacy/requests")) {
      await fulfill(route, 200, { generated_at: now, requests: items })
      return
    }
    if (request.method() === "PATCH" && path.includes("/v1/admin/privacy/requests/")) {
      const body = request.postDataJSON() as { status: string; resolution_note: string | null }
      patches.push(body)
      const id = path.split("/").pop()
      const index = items.findIndex((item) => item.id === id)
      const current = items[index]
      if (!current) {
        await fulfill(route, 404, { error: { code: "not_found", message: "x", request_id: "r" } })
        return
      }
      const closed = body.status === "done" || body.status === "rejected"
      const updated = {
        ...current,
        status: body.status,
        resolution_note: body.resolution_note ?? current.resolution_note,
        closed_at: closed ? now : null,
        overdue: closed ? false : current.overdue,
      }
      items[index] = updated
      await fulfill(route, 200, updated)
      return
    }
    await fulfill(route, 404, { error: { code: "not_found", message: "x", request_id: "r" } })
  })

  await page.goto("/admin/privacy")
  await expect(
    page.getByRole("heading", { level: 1, name: pt.pages.privacyRequests }),
  ).toBeVisible()
  const table = page.getByRole("table", { name: t.table.caption })
  const firstRow = table.getByRole("row").nth(1)
  await expect(firstRow).toContainText(pt.privacyRequest.types.deletion)
  await expect(firstRow).toContainText(pt.dueDate.overdueMany.replace("{n}", "5"))
  await expectNoSeriousViolations(page)

  await page
    .getByRole("button", {
      name: `${t.table.open}: ${pt.privacyRequest.types.deletion}, visitante@example.com`,
    })
    .click()
  const sheet = page.getByRole("dialog", {
    name: d.title.replace("{type}", pt.privacyRequest.types.deletion),
  })
  await expect(sheet).toBeVisible()
  await expectNoSeriousViolations(page)

  await sheet.getByRole("radio", { name: t.status.in_progress }).click()
  await sheet.getByRole("button", { name: d.save }).click()
  await expect(sheet.getByRole("status")).toContainText(
    d.saved.replace("{status}", t.status.in_progress),
  )

  await sheet.getByRole("radio", { name: t.status.done }).click()
  await sheet.getByLabel(d.note).fill("Conversa apagada e titular avisado por e-mail.")
  await sheet.getByRole("button", { name: d.save }).click()
  await expect(sheet.getByText(d.closedNotice)).toBeVisible()
  expect(patches).toEqual([
    { status: "in_progress", resolution_note: null },
    { status: "done", resolution_note: "Conversa apagada e titular avisado por e-mail." },
  ])
  await expectNoSeriousViolations(page)
})
