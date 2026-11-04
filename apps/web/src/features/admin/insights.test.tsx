import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import axe from "axe-core"
import { createMemoryRouter, RouterProvider } from "react-router"
import { describe, expect, it, vi } from "vitest"

import { AppProviders } from "@/app/providers.tsx"
import { routes } from "@/app/router.tsx"
import { pt } from "@/i18n/pt.ts"

import { delta, type Overview, type Quality } from "./insights-model.ts"

const t = pt.insights
const q = pt.quality

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

function overview(period = 7): Overview {
  return {
    period_days: period,
    generated_at: "2031-01-15T12:00:00Z",
    questions: { current: 1234, previous: 1000 },
    answer_rate: { current: 0.5, previous: 0.6 },
    abstention_rate: { current: 0.25, previous: 0.2 },
    helpful_rate: { current: 0.5, previous: null },
    trend: [
      { date: "2031-01-14", questions: 10, answered: 6 },
      { date: "2031-01-15", questions: 4, answered: 2 },
    ],
    outcomes: { answered: 2, abstained: 1, refused: 1, grounding_failed: 0, off_topic: 0, cancelled: 0, degraded: 0, error: 0 },
    intents: { public_info: 3, medical_advice: 1, off_topic: 0 },
    feedback: { helpful: 1, not_helpful: 1, none: 2 },
    funnel: [
      { step: "started", chat: 2, form: 1 },
      { step: "password_set", chat: 1, form: 1 },
      { step: "completed", chat: 1, form: 1 },
    ],
    budget: { used_tokens: 850, daily_budget: 1000, ratio: 0.85 },
  }
}

const guest = {
  id: "00000000-0000-4000-8000-000000000201",
  subject_kind: "guest" as const,
  pseudonym: "a1b2c3d4",
  started_at: "2031-01-15T10:00:00Z",
  last_activity_at: "2031-01-15T11:00:00Z",
  questions: 2,
  last_outcome: "abstained",
  helpful: 1,
  not_helpful: 0,
}
const member = {
  ...guest,
  id: "00000000-0000-4000-8000-000000000202",
  subject_kind: "member" as const,
  pseudonym: "e5f6a7b8",
  last_outcome: "answered",
  helpful: 0,
  not_helpful: 1,
}

const quality: Quality = {
  period_days: 7,
  outcomes: overview().outcomes,
  feedback: overview().feedback,
  conversations: [guest, member],
}

function inspection(subject: typeof guest | typeof member) {
  return {
    id: subject.id,
    subject_kind: subject.subject_kind,
    pseudonym: subject.pseudonym,
    created_at: subject.started_at,
    messages: [
      {
        id: "m-1", role: "user", content: "Horário de visita?", created_at: subject.started_at,
        outcome: null, prompt_version: null, model: null, request_id: "req-1", latency_ms: null,
        run_id: null, trace_url: null, citations: [], rating: null,
      },
      {
        id: "m-2", role: "assistant", content: "11h às 20h [1]", created_at: subject.started_at,
        outcome: "answered", prompt_version: "qa-v1", model: "fake", request_id: "req-1",
        latency_ms: 420, run_id: "00000000-0000-4000-8000-000000000999",
        trace_url: "https://smith.example/r/00000000-0000-4000-8000-000000000999",
        citations: [{ index: 1, document_title: "Visitas", heading: "Horário" }], rating: 1,
      },
    ],
  }
}

type Call = { method: string; path: string; search: string; body: unknown }

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  })
}

function installApi(handlers: Record<string, (call: Call) => Response> = {}) {
  const calls: Call[] = []
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const request = input instanceof Request ? input : new Request(String(input))
      const url = new URL(request.url)
      const path = url.pathname.replace("/backend", "")
      const text = request.method === "GET" ? "" : await request.text()
      const call = { method: request.method, path, search: url.search, body: text ? JSON.parse(text) : null }
      calls.push(call)
      if (path === "/v1/me") {
        return json(admin)
      }
      const handler = handlers[`${request.method} ${path}`]
      if (handler) {
        return handler(call)
      }
      if (path === "/v1/admin/overview") {
        return json(overview(Number(url.searchParams.get("period_days") ?? "7")))
      }
      if (path === "/v1/admin/quality") {
        return json(quality)
      }
      if (path === `/v1/admin/conversations/${guest.id}`) {
        return json(inspection(guest))
      }
      if (path === `/v1/admin/conversations/${member.id}`) {
        return json(inspection(member))
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

describe("regras dos indicadores", () => {
  it("compara contagem em porcentagem e taxa em pontos percentuais", () => {
    expect(delta({ current: 1234, previous: 1000 }, "count")).toEqual({
      direction: "up",
      text: t.delta.up.replace("{value}", "23,4%"),
    })
    expect(delta({ current: 0.5, previous: 0.6 }, "rate")).toEqual({
      direction: "down",
      text: t.delta.down.replace("{value}", "10 p.p."),
    })
    expect(delta({ current: 0.5, previous: null }, "rate").direction).toBe("none")
    expect(delta({ current: 3, previous: 0 }, "count").direction).toBe("none")
  })
})

describe("visão geral", () => {
  it("mostra os quatro indicadores com o valor final no aria-label (M2)", async () => {
    installApi()
    renderAt("/admin")
    const questions = await screen.findByRole("group", { name: /^Perguntas: 1\.234\./ })
    expect(within(questions).getByText("1.234")).toBeInTheDocument()
    expect(questions).toHaveAccessibleName(
      t.stats.ariaLabel
        .replace("{label}", t.stats.questions)
        .replace("{value}", "1.234")
        .replace("{delta}", t.delta.up.replace("{value}", "23,4%")),
    )
    expect(screen.getByRole("group", { name: /^Taxa de respostas: 50%/ })).toBeInTheDocument()
    expect(screen.getByRole("group", { name: /^Taxa de abstenção: 25%/ })).toBeInTheDocument()
    expect(
      screen.getByRole("group", { name: new RegExp(`^Taxa de útil: 50%\\. ${t.delta.none}`) }),
    ).toBeInTheDocument()
  })

  it("dá tabelas equivalentes aos gráficos e o orçamento perto do limite", async () => {
    installApi()
    renderAt("/admin")
    const trend = await screen.findByRole("table", { name: t.trend.tableCaption })
    expect(within(trend).getAllByRole("row")).toHaveLength(3)
    const funnel = screen.getByRole("table", { name: t.funnel.tableCaption })
    const started = within(funnel).getByRole("row", { name: new RegExp(t.funnel.steps.started) })
    expect(started).toHaveTextContent("21")
    expect(screen.getByText(t.budget.nearLimit)).toBeInTheDocument()
    expect(screen.getByRole("progressbar", { name: t.budget.label })).toBeInTheDocument()
    const outcomes = screen.getByRole("list", { name: t.outcomesCard.outcome })
    expect(within(outcomes).getByText(t.outcomes.answered)).toBeInTheDocument()
    expect(outcomes).toHaveTextContent("50%")
  })

  it("troca as abas de desfecho e o período", async () => {
    const calls = installApi()
    const user = userEvent.setup()
    renderAt("/admin")
    await screen.findByRole("table", { name: t.trend.tableCaption })
    await user.click(screen.getByRole("tab", { name: t.outcomesCard.intent }))
    const intents = screen.getByRole("list", { name: t.outcomesCard.intent })
    expect(within(intents).getByText(t.intents.medical_advice)).toBeInTheDocument()
    await user.click(screen.getByRole("radio", { name: t.period.days30 }))
    await waitFor(() => {
      expect(calls.some((call) => call.search === "?period_days=30")).toBe(true)
    })
  })

  it("passa no axe sem violação séria", async () => {
    installApi()
    const { container } = renderAt("/admin")
    await screen.findByRole("table", { name: t.trend.tableCaption })
    expect(await seriousViolations(container)).toEqual([])
  })
})

describe("qualidade", () => {
  it("lista conversas pseudonimizadas e filtra por feedback", async () => {
    const calls = installApi()
    const user = userEvent.setup()
    renderAt("/admin/quality")
    const table = await screen.findByRole("table", { name: q.table.caption })
    await within(table).findByText("a1b2c3d4")
    expect(within(table).queryByText(/@/)).not.toBeInTheDocument()
    await user.click(screen.getByRole("radio", { name: t.feedback.not_helpful }))
    await waitFor(() => {
      expect(calls.some((call) => call.search.includes("feedback=not_helpful"))).toBe(true)
    })
  })

  it("J7: da lista ao rastro do LangSmith em dois cliques", async () => {
    installApi()
    const user = userEvent.setup()
    renderAt("/admin/quality")
    await screen.findByText("a1b2c3d4")
    await user.click(
      screen.getByRole("button", { name: `${q.table.open}: ${q.subject.guest} a1b2c3d4` }),
    )
    const sheet = await screen.findByRole("dialog", {
      name: q.inspector.title.replace("{pseudonym}", "a1b2c3d4"),
    })
    const trace = await within(sheet).findByRole("link", { name: q.inspector.trace })
    expect(trace).toHaveAttribute("href", "https://smith.example/r/00000000-0000-4000-8000-000000000999")
    expect(within(sheet).getByText(q.inspector.promptVersion.replace("{version}", "qa-v1"))).toBeInTheDocument()
    expect(within(sheet).getByText(q.reveal.guestHint)).toBeInTheDocument()
    expect(within(sheet).queryByRole("button", { name: q.reveal.action })).not.toBeInTheDocument()
  })

  it("revela a identidade só com motivo", async () => {
    const calls = installApi({
      [`POST /v1/admin/conversations/${member.id}/reveal`]: () =>
        json({ conversation_id: member.id, full_name: "Ana Costa", email: "ana@example.com" }),
    })
    const user = userEvent.setup()
    renderAt("/admin/quality")
    await screen.findByText("e5f6a7b8")
    await user.click(
      screen.getByRole("button", { name: `${q.table.open}: ${q.subject.member} e5f6a7b8` }),
    )
    const sheet = await screen.findByRole("dialog")
    await user.click(await within(sheet).findByRole("button", { name: q.reveal.action }))
    await user.type(within(sheet).getByLabelText(q.reveal.reason), "curto")
    await user.click(within(sheet).getByRole("button", { name: q.reveal.confirm }))
    expect(within(sheet).getByText(q.reveal.reasonInvalid)).toBeInTheDocument()
    expect(calls.some((call) => call.method === "POST")).toBe(false)

    await user.clear(within(sheet).getByLabelText(q.reveal.reason))
    await user.type(within(sheet).getByLabelText(q.reveal.reason), "Pedido de titular número 12")
    await user.click(within(sheet).getByRole("button", { name: q.reveal.confirm }))
    expect(await within(sheet).findByText("Ana Costa · ana@example.com")).toBeInTheDocument()
    expect(calls.find((call) => call.method === "POST")?.body).toEqual({
      reason: "Pedido de titular número 12",
    })
  })

  it("passa no axe sem violação séria", async () => {
    installApi()
    const { container } = renderAt("/admin/quality")
    await screen.findByText("a1b2c3d4")
    expect(await seriousViolations(container)).toEqual([])
  })
})
