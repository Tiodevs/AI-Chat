import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import axe from "axe-core"
import { createMemoryRouter, RouterProvider } from "react-router"
import { describe, expect, it, vi } from "vitest"

import { AppProviders } from "@/app/providers.tsx"
import { routes } from "@/app/router.tsx"
import { dueState } from "@/components/patterns/due-date-badge.tsx"
import { pt } from "@/i18n/pt.ts"

import { mailtoHref, type PrivacyQueue, type PrivacyQueueItem } from "./privacy-queue-model.ts"

const t = pt.privacyQueue
const d = pt.privacyQueue.detail
const now = "2031-01-15T12:00:00Z"

const admin = {
  id: "00000000-0000-4000-8000-0000000000ad",
  email: "admin@example.com",
  full_name: "Admin Teste",
  phone: null,
  visitor_type: null,
  visit_reason: null,
  role: "admin",
  needs_legal_acceptance: false,
}

function item(overrides: Partial<PrivacyQueueItem>): PrivacyQueueItem {
  return {
    id: "00000000-0000-4000-8000-000000000301",
    request_type: "deletion",
    status: "open",
    contact_email: "titular@example.com",
    description: "Quero apagar a minha conversa de convidado.",
    received_at: "2030-12-26T12:00:00Z",
    due_at: "2031-01-10T12:00:00Z",
    closed_at: null,
    resolution_note: null,
    overdue: true,
    linked_account: false,
    ...overrides,
  }
}

// A ordem é a do servidor: atrasados, depois no prazo, depois fechados.
function fixtures(): PrivacyQueueItem[] {
  return [
    item({}),
    item({
      id: "00000000-0000-4000-8000-000000000302",
      request_type: "access",
      status: "in_progress",
      contact_email: "acesso@example.com",
      due_at: "2031-01-17T12:00:00Z",
      overdue: false,
      linked_account: true,
    }),
    item({
      id: "00000000-0000-4000-8000-000000000303",
      request_type: "correction",
      contact_email: "correcao@example.com",
      due_at: "2031-01-29T12:00:00Z",
      overdue: false,
    }),
    item({
      id: "00000000-0000-4000-8000-000000000304",
      request_type: "objection",
      status: "done",
      contact_email: "oposicao@example.com",
      due_at: "2031-01-20T12:00:00Z",
      closed_at: "2031-01-12T15:00:00Z",
      resolution_note: "Tratamento encerrado.",
      overdue: false,
    }),
  ]
}

type Call = { method: string; path: string; body: unknown }

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  })
}

function installApi(patch?: (call: Call, items: PrivacyQueueItem[]) => Response) {
  const calls: Call[] = []
  const items = fixtures()
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const request = input instanceof Request ? input : new Request(String(input))
      const path = new URL(request.url).pathname.replace("/backend", "")
      const text = request.method === "GET" ? "" : await request.text()
      const call = { method: request.method, path, body: text ? JSON.parse(text) : null }
      calls.push(call)
      if (path === "/v1/me") {
        return json(admin)
      }
      if (request.method === "GET" && path === "/v1/admin/privacy/requests") {
        const queue: PrivacyQueue = { generated_at: now, requests: items }
        return json(queue)
      }
      if (request.method === "PATCH" && path.startsWith("/v1/admin/privacy/requests/")) {
        if (patch) {
          return patch(call, items)
        }
        const id = path.split("/").pop()
        const index = items.findIndex((entry) => entry.id === id)
        const body = call.body as { status: string; resolution_note: string | null }
        const closed = body.status === "done" || body.status === "rejected"
        const current = items[index]
        if (!current) {
          return json({ error: { code: "not_found", message: "x", request_id: "r" } }, 404)
        }
        const updated = {
          ...current,
          status: body.status,
          resolution_note: body.resolution_note ?? current.resolution_note,
          closed_at: closed ? now : null,
          overdue: closed ? false : current.overdue,
        }
        items[index] = updated
        return json(updated)
      }
      return json({ error: { code: "not_found", message: "x", request_id: "r" } }, 404)
    }),
  )
  return calls
}

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  return render(
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>,
  )
}

async function seriousViolations(container: HTMLElement) {
  const result = await axe.run(container, { resultTypes: ["violations"] })
  return result.violations
    .filter((violation) => violation.impact === "serious" || violation.impact === "critical")
    .map((violation) => violation.id)
}

function openButton(type: string, email: string) {
  return screen.findByRole("button", { name: `${t.table.open}: ${type}, ${email}` })
}

describe("prazo do pedido de titular", () => {
  it("diz em texto se está atrasado, perto do prazo, no prazo ou fechado", () => {
    expect(dueState({ dueAt: "2031-01-10T12:00:00Z", closedAt: null, now })).toEqual({
      kind: "overdue",
      days: 5,
      text: pt.dueDate.overdueMany.replace("{n}", "5"),
    })
    expect(dueState({ dueAt: "2031-01-14T11:00:00Z", closedAt: null, now }).text).toBe(
      pt.dueDate.overdueOne,
    )
    expect(dueState({ dueAt: "2031-01-15T09:00:00Z", closedAt: null, now }).text).toBe(
      pt.dueDate.overdueToday,
    )
    expect(dueState({ dueAt: "2031-01-15T18:00:00Z", closedAt: null, now })).toMatchObject({
      kind: "soon",
      text: pt.dueDate.dueToday,
    })
    expect(dueState({ dueAt: "2031-01-18T12:00:00Z", closedAt: null, now }).kind).toBe("soon")
    expect(dueState({ dueAt: "2031-01-19T12:00:00Z", closedAt: null, now })).toMatchObject({
      kind: "ok",
      text: pt.dueDate.dueMany.replace("{n}", "4"),
    })
    expect(
      dueState({ dueAt: "2031-01-10T12:00:00Z", closedAt: "2031-01-12T15:00:00Z", now }).kind,
    ).toBe("closed")
  })
})

describe("contato do titular", () => {
  it("só vira link mailto um endereço que o cliente de e-mail não pode partir", () => {
    expect(mailtoHref("ana.souza+dsr@example.com")).toBe("mailto:ana.souza+dsr@example.com")
    expect(mailtoHref("vitima@example.com?bcc=atacante@evil.com")).toBeNull()
    expect(mailtoHref("vitima@example.com,atacante@evil.com")).toBeNull()
    expect(mailtoHref("vitima@example.com;atacante@evil.com")).toBeNull()
  })
})

describe("pedidos de titular", () => {
  it("mostra os atrasados primeiro, com texto e não só cor (FR-16)", async () => {
    installApi()
    renderAt("/admin/privacy")
    const table = await screen.findByRole("table", { name: t.table.caption })
    await within(table).findByText("titular@example.com")
    const rows = within(table).getAllByRole("row").slice(1)
    expect(rows).toHaveLength(4)
    const first = rows[0]
    if (!first) {
      throw new Error("missing row")
    }
    expect(within(first).getByRole("rowheader")).toHaveTextContent(
      pt.privacyRequest.types.deletion,
    )
    expect(within(first).getByText(pt.dueDate.overdueMany.replace("{n}", "5"))).toBeInTheDocument()
    expect(first.querySelector("[data-due]")).toHaveAttribute("data-due", "overdue")
    // Atrasado em --danger e prazo próximo em --warning, sempre com o texto ao lado.
    expect(first.querySelector("[data-due] [data-slot=badge]")).toHaveAttribute("data-variant", "danger")
    expect(within(rows[1] as HTMLElement).getByText(pt.dueDate.dueMany.replace("{n}", "2"))).toBeInTheDocument()
    expect(rows[1]?.querySelector("[data-due]")).toHaveAttribute("data-due", "soon")
    expect(rows[1]?.querySelector("[data-due] [data-slot=badge]")).toHaveAttribute("data-variant", "warning")
    expect(rows[2]?.querySelector("[data-due] [data-slot=badge]")).toHaveAttribute("data-variant", "secondary")
    expect(within(rows[3] as HTMLElement).getByText(t.status.done)).toBeInTheDocument()
    const summary = screen.getByRole("region", { name: t.summary.label })
    expect(within(summary).getByText(t.summary.overdue).closest("div")).toHaveTextContent(
      new RegExp(`^${t.summary.overdue}1$`),
    )
    expect(within(summary).getByText(t.summary.open).closest("div")).toHaveTextContent(
      new RegExp(`^${t.summary.open}2$`),
    )
  })

  it("muda para em andamento e conclui com nota, sem nota não envia", async () => {
    const calls = installApi()
    const user = userEvent.setup()
    renderAt("/admin/privacy")
    await screen.findByRole("table", { name: t.table.caption })
    await user.click(await openButton(pt.privacyRequest.types.deletion, "titular@example.com"))
    const sheet = await screen.findByRole("dialog", {
      name: d.title.replace("{type}", pt.privacyRequest.types.deletion),
    })
    expect(within(sheet).getByText("Quero apagar a minha conversa de convidado.")).toBeInTheDocument()

    await user.click(within(sheet).getByRole("radio", { name: t.status.in_progress }))
    await user.click(within(sheet).getByRole("button", { name: d.save }))
    expect(
      await within(sheet).findByText(d.saved.replace("{status}", t.status.in_progress)),
    ).toBeInTheDocument()
    const patches = () => calls.filter((call) => call.method === "PATCH")
    expect(patches()).toHaveLength(1)
    expect(patches()[0]?.body).toEqual({ status: "in_progress", resolution_note: null })

    await user.click(within(sheet).getByRole("radio", { name: t.status.done }))
    await user.click(within(sheet).getByRole("button", { name: d.save }))
    expect(within(sheet).getByText(d.noteRequired)).toBeInTheDocument()
    expect(within(sheet).getByLabelText(d.note)).toHaveAttribute("aria-invalid", "true")
    expect(patches()).toHaveLength(1)

    await user.type(within(sheet).getByLabelText(d.note), "Conversa apagada e titular avisado.")
    await user.click(within(sheet).getByRole("button", { name: d.save }))
    expect(
      await within(sheet).findByText(d.saved.replace("{status}", t.status.done)),
    ).toBeInTheDocument()
    expect(patches()[1]?.body).toEqual({
      status: "done",
      resolution_note: "Conversa apagada e titular avisado.",
    })
    // Fechado, o pedido mostra a nota e não oferece mais o formulário. O foco vai para a nota.
    expect(await within(sheet).findByText(d.closedNotice)).toBeInTheDocument()
    expect(within(sheet).queryByRole("button", { name: d.save })).not.toBeInTheDocument()
    await waitFor(() => {
      expect(within(sheet).getByRole("heading", { name: d.note })).toHaveFocus()
    })
  })

  it("mostra o erro de campo do servidor e o request_id de outras falhas", async () => {
    const calls = installApi((call) =>
      (call.body as { status: string }).status === "rejected"
        ? json(
            {
              error: {
                code: "validation_error",
                message: "x",
                request_id: "r1",
                field_errors: { resolution_note: "Nota recusada pelo servidor." },
              },
            },
            422,
          )
        : json({ error: { code: "conflict", message: "Este pedido já foi fechado.", request_id: "01REQ" } }, 409),
    )
    const user = userEvent.setup()
    renderAt("/admin/privacy")
    await screen.findByRole("table", { name: t.table.caption })
    await user.click(await openButton(pt.privacyRequest.types.correction, "correcao@example.com"))
    const sheet = await screen.findByRole("dialog")
    await user.click(within(sheet).getByRole("radio", { name: t.status.rejected }))
    await user.type(within(sheet).getByLabelText(d.note), "Fora do escopo.")
    await user.click(within(sheet).getByRole("button", { name: d.save }))
    expect(await within(sheet).findByText("Nota recusada pelo servidor.")).toBeInTheDocument()

    const reads = () =>
      calls.filter((call) => call.method === "GET" && call.path === "/v1/admin/privacy/requests").length
    const before = reads()
    await user.click(within(sheet).getByRole("radio", { name: t.status.in_progress }))
    await user.click(within(sheet).getByRole("button", { name: d.save }))
    expect(await within(sheet).findByRole("alert")).toHaveTextContent("Este pedido já foi fechado.")
    expect(within(sheet).getByText("01REQ")).toBeInTheDocument()
    // Depois de um 409, a fila é relida para o detalhe não ficar velho.
    await waitFor(() => {
      expect(reads()).toBeGreaterThan(before)
    })
  })

  it("um pedido fechado abre só para leitura", async () => {
    installApi()
    const user = userEvent.setup()
    renderAt("/admin/privacy")
    await screen.findByRole("table", { name: t.table.caption })
    await user.click(await openButton(pt.privacyRequest.types.objection, "oposicao@example.com"))
    const sheet = await screen.findByRole("dialog")
    expect(within(sheet).getByRole("link", { name: "oposicao@example.com" })).toHaveAttribute(
      "href",
      "mailto:oposicao@example.com",
    )
    expect(within(sheet).getByText("Tratamento encerrado.")).toBeInTheDocument()
    expect(within(sheet).getByText(d.closedNotice)).toBeInTheDocument()
    expect(within(sheet).queryByRole("radio")).not.toBeInTheDocument()
  })

  it("passa no axe sem violação séria, na lista e no detalhe", async () => {
    installApi()
    const user = userEvent.setup()
    const { container } = renderAt("/admin/privacy")
    await screen.findByRole("table", { name: t.table.caption })
    expect(await seriousViolations(container)).toEqual([])
    await user.click(await openButton(pt.privacyRequest.types.access, "acesso@example.com"))
    const sheet = await screen.findByRole("dialog")
    await waitFor(() => {
      expect(within(sheet).getByRole("radio", { name: t.status.in_progress })).toBeInTheDocument()
    })
    expect(await seriousViolations(document.body)).toEqual([])
  })
})
