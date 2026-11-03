import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import axe from "axe-core"
import { createMemoryRouter, RouterProvider } from "react-router"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { AppProviders } from "@/app/providers.tsx"
import { queryClient } from "@/app/query-client.ts"
import { routes } from "@/app/router.tsx"
import { pt } from "@/i18n/pt.ts"

import {
  deleteConfirmed,
  profileDefaults,
  profilePatch,
  profileSchema,
} from "./model.ts"

const member = {
  id: "00000000-0000-0000-0000-000000000002",
  email: "ana@example.com",
  full_name: "Ana Souza",
  phone: null as string | null,
  visitor_type: null as string | null,
  visit_reason: null as string | null,
  role: "member" as "member" | "admin",
  needs_legal_acceptance: false,
}

const granted = "2026-11-03T12:00:00.000Z"

function consentsBody(options: { personalization?: boolean; quality?: boolean }) {
  const state = (purpose: string, on: boolean) => ({
    purpose,
    granted: on,
    document_version: on ? "2026-10-25.1" : null,
    granted_at: on ? granted : null,
  })
  return {
    current: [
      state("terms_and_privacy_notice", true),
      state("age_18_plus", true),
      state("profile_personalization", options.personalization ?? false),
      state("quality_improvement", options.quality ?? false),
    ],
    history: [],
  }
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  })
}

type Call = { method: string; path: string; body: unknown }

type Handler = (call: Call) => Response | Promise<Response>

function installApi(handlers: Record<string, Handler>) {
  const calls: Call[] = []
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const request =
        input instanceof Request ? input : new Request(String(input))
      const path = new URL(request.url).pathname.replace("/backend", "")
      const text = request.method === "GET" ? "" : await request.text()
      const call: Call = {
        method: request.method,
        path,
        body: text ? JSON.parse(text) : null,
      }
      calls.push(call)
      const handler = handlers[`${request.method} ${path}`]
      if (!handler) {
        return json({ error: { code: "not_found", message: "?" } }, 404)
      }
      return handler(call)
    }),
  )
  return calls
}

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  const view = render(
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>,
  )
  return { router, ...view }
}

const baseHandlers = (user = member): Record<string, Handler> => ({
  "GET /v1/me": () => json(user),
  "GET /v1/me/consents": () => json(consentsBody({})),
  "GET /v1/conversations": () => json({ conversations: [] }),
})

beforeEach(() => {
  queryClient.clear()
  localStorage.clear()
})

describe("regras do perfil", () => {
  it("valida o nome e o telefone como o servidor", () => {
    const defaults = profileDefaults(member)
    expect(profileSchema.safeParse(defaults).success).toBe(true)
    expect(profileSchema.safeParse({ ...defaults, full_name: "A" }).success).toBe(
      false,
    )
    expect(profileSchema.safeParse({ ...defaults, phone: "abc" }).success).toBe(
      false,
    )
    expect(profileSchema.safeParse({ ...defaults, phone: "" }).success).toBe(true)
  })

  it("só envia os campos sensíveis com a personalização ativa", () => {
    const values = {
      full_name: " Ana ",
      phone: "",
      visitor_type: "patient",
      visit_reason: "",
    }
    expect(profilePatch(values, false)).toEqual({
      full_name: "Ana",
      phone: null,
    })
    expect(profilePatch(values, true)).toEqual({
      full_name: "Ana",
      phone: null,
      visitor_type: "patient",
      visit_reason: null,
    })
  })

  it("a exclusão pede a palavra exata", () => {
    expect(deleteConfirmed("EXCLUIR")).toBe(true)
    expect(deleteConfirmed(" EXCLUIR ")).toBe(true)
    expect(deleteConfirmed("excluir")).toBe(false)
    expect(deleteConfirmed("")).toBe(false)
  })
})

describe("aba Perfil", () => {
  it("corrige o nome e mostra a confirmação", async () => {
    const user = userEvent.setup()
    const calls = installApi({
      ...baseHandlers(),
      "PATCH /v1/me": ({ body }) =>
        json({ ...member, ...(body as object) }),
    })
    renderAt("/account")
    const name = await screen.findByLabelText(pt.account.profile.fullName)
    expect(name).toHaveValue("Ana Souza")
    await user.clear(name)
    await user.type(name, "Maria Nova")
    await user.click(
      screen.getByRole("button", { name: pt.account.profile.save }),
    )
    expect(await screen.findByText(pt.account.profile.saved)).toBeInTheDocument()
    const patch = calls.find((call) => call.method === "PATCH")
    expect(patch?.body).toEqual({ full_name: "Maria Nova", phone: null })
  })

  it("mostra o erro de campo devolvido pelo servidor", async () => {
    const user = userEvent.setup()
    installApi({
      ...baseHandlers(),
      "PATCH /v1/me": () =>
        json(
          {
            error: {
              code: "validation_error",
              message: "Não foi possível salvar o perfil.",
              request_id: "01ACC",
              field_errors: { phone: "Telefone recusado pelo servidor." },
            },
          },
          422,
        ),
    })
    renderAt("/account")
    await screen.findByLabelText(pt.account.profile.fullName)
    await user.type(screen.getByLabelText(pt.account.profile.phone), "5550142600")
    await user.click(
      screen.getByRole("button", { name: pt.account.profile.save }),
    )
    expect(
      await screen.findByText("Telefone recusado pelo servidor."),
    ).toBeInTheDocument()
  })

  it("esconde tipo de visitante e motivo sem a personalização", async () => {
    installApi(baseHandlers())
    renderAt("/account")
    await screen.findByLabelText(pt.account.profile.fullName)
    expect(await screen.findByText(pt.account.profile.sensitiveOff)).toBeVisible()
    expect(
      screen.queryByRole("radio", { name: pt.registration.visitorTypes.patient }),
    ).not.toBeInTheDocument()
  })

  it("mostra os campos sensíveis com a personalização ativa", async () => {
    installApi({
      ...baseHandlers({ ...member, visitor_type: "patient" }),
      "GET /v1/me/consents": () => json(consentsBody({ personalization: true })),
    })
    renderAt("/account")
    expect(
      await screen.findByRole("radio", { name: pt.registration.visitorTypes.patient }),
    ).toBeChecked()
    expect(
      screen.getByRole("radio", { name: pt.registration.visitReasons.own_appointment }),
    ).toBeInTheDocument()
  })

  it("guarda a preferência de movimento", async () => {
    const user = userEvent.setup()
    installApi(baseHandlers())
    renderAt("/account")
    await screen.findByLabelText(pt.account.profile.fullName)
    await user.click(screen.getByRole("radio", { name: pt.profile.motionReduce }))
    expect(localStorage.getItem("atrium.motion-preference")).toBe("on")
    expect(document.documentElement.dataset.motion).toBe("reduce")
  })
})

describe("aba Conversas", () => {
  it("lista a data e a primeira pergunta", async () => {
    const user = userEvent.setup()
    installApi({
      ...baseHandlers(),
      "GET /v1/conversations": () =>
        json({
          conversations: [
            {
              id: "00000000-0000-4000-8000-0000000000a1",
              created_at: granted,
              first_question: "Qual é o horário de visita?",
            },
          ],
        }),
    })
    renderAt("/account")
    await user.click(
      await screen.findByRole("tab", { name: pt.account.tabs.conversations }),
    )
    const list = await screen.findByRole("list", {
      name: pt.account.conversations.listLabel,
    })
    const link = within(list).getByRole("link", {
      name: /Qual é o horário de visita\?/,
    })
    expect(link).toHaveAttribute(
      "href",
      "/ask/00000000-0000-4000-8000-0000000000a1",
    )
  })

  it("mostra o estado vazio", async () => {
    const user = userEvent.setup()
    installApi(baseHandlers())
    renderAt("/account")
    await user.click(
      await screen.findByRole("tab", { name: pt.account.tabs.conversations }),
    )
    expect(
      await screen.findByText(pt.account.conversations.empty),
    ).toBeInTheDocument()
  })
})

describe("aba Privacidade", () => {
  async function openPrivacy(user: ReturnType<typeof userEvent.setup>) {
    renderAt("/account")
    await user.click(
      await screen.findByRole("tab", { name: pt.account.tabs.privacy }),
    )
  }

  it("liga e desliga um consentimento opcional", async () => {
    const user = userEvent.setup()
    let personalization = false
    const calls = installApi({
      ...baseHandlers(),
      "GET /v1/me/consents": () => json(consentsBody({ personalization })),
      "PUT /v1/me/consents/profile_personalization": ({ body }) => {
        personalization = (body as { granted: boolean }).granted
        return json(consentsBody({ personalization }))
      },
    })
    await openPrivacy(user)
    const toggle = await screen.findByRole("switch", {
      name: pt.account.privacy.personalization,
    })
    expect(toggle).not.toBeChecked()
    await user.click(toggle)
    await waitFor(() => expect(toggle).toBeChecked())
    await user.click(toggle)
    await waitFor(() => expect(toggle).not.toBeChecked())
    const puts = calls.filter((call) => call.method === "PUT")
    expect(puts.map((call) => call.body)).toEqual([
      { granted: true },
      { granted: false },
    ])
  })

  it("mostra a data de aceite e a versão dos Termos", async () => {
    const user = userEvent.setup()
    installApi({
      ...baseHandlers(),
      "GET /v1/me/consents": () => json(consentsBody({ quality: true })),
    })
    await openPrivacy(user)
    expect(
      await screen.findByText(/Versão 2026-10-25\.1/),
    ).toBeInTheDocument()
    expect(screen.getByRole("switch", { name: pt.account.privacy.quality })).toBeChecked()
  })

  it("exporta os dados em um arquivo JSON", async () => {
    const user = userEvent.setup()
    const createUrl = vi.fn(() => "blob:atrium")
    Object.assign(URL, { createObjectURL: createUrl, revokeObjectURL: vi.fn() })
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined)
    const calls = installApi({
      ...baseHandlers(),
      "GET /v1/me/export": () =>
        new Response(JSON.stringify({ profile: {} }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
    })
    await openPrivacy(user)
    await user.click(
      await screen.findByRole("button", { name: pt.account.privacy.exportButton }),
    )
    expect(await screen.findByText(pt.account.privacy.exported)).toBeInTheDocument()
    expect(calls.some((call) => call.path === "/v1/me/export")).toBe(true)
    expect(createUrl).toHaveBeenCalled()
    expect(click).toHaveBeenCalled()
    click.mockRestore()
  })

  it("só exclui depois de digitar EXCLUIR", async () => {
    const user = userEvent.setup()
    const calls = installApi({
      ...baseHandlers(),
      "DELETE /v1/me": () => new Response(null, { status: 204 }),
    })
    const { router } = renderAt("/account")
    await user.click(
      await screen.findByRole("tab", { name: pt.account.tabs.privacy }),
    )
    await user.click(
      await screen.findByRole("button", { name: pt.account.privacy.deleteButton }),
    )
    const dialog = await screen.findByRole("alertdialog")
    const confirm = within(dialog).getByRole("button", {
      name: pt.account.privacy.deleteConfirm,
    })
    expect(confirm).toBeDisabled()
    await user.type(
      within(dialog).getByLabelText(pt.account.privacy.deleteConfirmLabel),
      "excluir",
    )
    expect(confirm).toBeDisabled()
    await user.clear(
      within(dialog).getByLabelText(pt.account.privacy.deleteConfirmLabel),
    )
    await user.type(
      within(dialog).getByLabelText(pt.account.privacy.deleteConfirmLabel),
      pt.account.privacy.deleteConfirmWord,
    )
    expect(confirm).toBeEnabled()
    await user.click(confirm)
    await waitFor(() => expect(router.state.location.pathname).toBe("/"))
    expect(calls.some((call) => call.method === "DELETE")).toBe(true)
  })

  it("mostra a recusa quando um admin tenta excluir a própria conta", async () => {
    const user = userEvent.setup()
    installApi({
      ...baseHandlers({ ...member, role: "admin" }),
      "DELETE /v1/me": () =>
        json(
          {
            error: {
              code: "forbidden",
              message: "Um admin não pode excluir a própria conta pela API.",
              request_id: "01ADM",
            },
          },
          403,
        ),
    })
    await openPrivacy(user)
    await user.click(
      await screen.findByRole("button", { name: pt.account.privacy.deleteButton }),
    )
    const dialog = await screen.findByRole("alertdialog")
    await user.type(
      within(dialog).getByLabelText(pt.account.privacy.deleteConfirmLabel),
      pt.account.privacy.deleteConfirmWord,
    )
    await user.click(
      within(dialog).getByRole("button", { name: pt.account.privacy.deleteConfirm }),
    )
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "Um admin não pode excluir a própria conta pela API.",
    )
  })

  it("não tem violação grave na conta", async () => {
    const user = userEvent.setup()
    installApi(baseHandlers())
    const { container } = render(
      <AppProviders>
        <RouterProvider
          router={createMemoryRouter(routes, { initialEntries: ["/account"] })}
        />
      </AppProviders>,
    )
    await screen.findByLabelText(pt.account.profile.fullName)
    let results = await axe.run(container, { resultTypes: ["violations"] })
    await user.click(screen.getByRole("tab", { name: pt.account.tabs.privacy }))
    await screen.findByRole("switch", { name: pt.account.privacy.quality })
    const privacy = await axe.run(container, { resultTypes: ["violations"] })
    results = {
      ...results,
      violations: [...results.violations, ...privacy.violations],
    }
    const serious = results.violations.filter(
      (violation) =>
        violation.impact === "serious" || violation.impact === "critical",
    )
    expect(serious.map((violation) => violation.id)).toEqual([])
  })
})

describe("novo aceite dos documentos legais", () => {
  it("leva o membro a /legal/accept na próxima entrada e volta depois do aceite", async () => {
    const user = userEvent.setup()
    const calls = installApi({
      ...baseHandlers({ ...member, needs_legal_acceptance: true }),
      "GET /v1/legal/versions": () =>
        json({ terms: "2026-12-01.1", privacy_notice: "2026-12-01.1" }),
      "PUT /v1/me/consents/terms_and_privacy_notice": () =>
        json(consentsBody({})),
    })
    const { router } = renderAt("/account")
    expect(
      await screen.findByRole("heading", { name: pt.pages.legalAccept }),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe("/legal/accept")
    expect(router.state.location.search).toBe(
      `?returnTo=${encodeURIComponent("/account")}`,
    )
    expect(await screen.findByText(/2026-12-01\.1/)).toBeInTheDocument()
    await user.click(
      screen.getByRole("button", { name: pt.legalAccept.accept }),
    )
    await waitFor(() => expect(router.state.location.pathname).toBe("/account"))
    expect(calls.find((call) => call.method === "PUT")?.body).toEqual({
      granted: true,
    })
  })

  it("o login com documento novo vai primeiro ao aceite", async () => {
    const user = userEvent.setup()
    installApi({
      "GET /v1/me": () =>
        json({ error: { code: "unauthenticated", message: "x", request_id: "1" } }, 401),
      "POST /v1/auth/login": () =>
        json({ ...member, needs_legal_acceptance: true }),
      "GET /v1/legal/versions": () =>
        json({ terms: "2026-12-01.1", privacy_notice: "2026-12-01.1" }),
    })
    const { router } = renderAt("/sign-in?returnTo=/account")
    await user.type(await screen.findByLabelText(pt.signIn.email), "ana@example.com")
    await user.type(screen.getByLabelText(pt.signIn.password), "correct-horse-1")
    await user.click(screen.getByRole("button", { name: pt.signIn.submit }))
    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/legal/accept"),
    )
    expect(router.state.location.search).toBe(
      `?returnTo=${encodeURIComponent("/account")}`,
    )
  })
})
