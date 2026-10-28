import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import axe from "axe-core"
import { createMemoryRouter, RouterProvider } from "react-router"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { AppProviders } from "@/app/providers.tsx"
import { queryClient } from "@/app/query-client.ts"
import { routes } from "@/app/router.tsx"
import { ApiRequestError } from "@/features/auth/api-error.ts"
import { limitMessage, safeReturnTo } from "@/features/auth/return-to.ts"
import { pt } from "@/i18n/pt.ts"

const admin = {
  id: "00000000-0000-0000-0000-000000000001",
  email: "admin@example.com",
  full_name: "Administrador",
  phone: null,
  visitor_type: null,
  visit_reason: null,
  role: "admin" as const,
  needs_legal_acceptance: true,
}

const member = { ...admin, id: "00000000-0000-0000-0000-000000000002", role: "member" as const }

function json(body: unknown, status: number) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  })
}

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  render(
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>,
  )
  return router
}

describe("retorno seguro", () => {
  it("aceita só caminhos da própria origem", () => {
    expect(safeReturnTo("/admin")).toBe("/admin")
    expect(safeReturnTo("/admin/documents?page=2")).toBe("/admin/documents?page=2")
    expect(safeReturnTo("https://evil.example")).toBe("/")
    expect(safeReturnTo("//evil.example")).toBe("/")
    expect(safeReturnTo(null)).toBe("/")
  })

  it("mostra o limite em minutos", () => {
    expect(limitMessage(30)).toBe(pt.signIn.limitedOne)
    expect(limitMessage(90)).toBe(
      pt.signIn.limitedMany.replace("{minutes}", "2"),
    )
  })
})

describe("entrar", () => {
  beforeEach(() => {
    queryClient.clear()
  })

  it("mostra o erro de credenciais e o de limite", async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const request = input instanceof Request ? input : new Request(String(input))
        if (!request.url.includes("/v1/auth/login")) {
          return json({ error: { code: "unauthenticated", message: pt.signIn.credentials, request_id: "01" } }, 401)
        }
        const body = (await request.json()) as { password?: string }
        if (body.password === "limite-limite") {
          return json(
            {
              error: {
                code: "rate_limited",
                message: pt.signIn.credentials,
                request_id: "01LIMIT",
                retry_after_seconds: 90,
              },
            },
            429,
          )
        }
        return json(
          {
            error: {
              code: "unauthenticated",
              message: pt.signIn.credentials,
              request_id: "01BAD",
            },
          },
          401,
        )
      }),
    )
    renderAt("/sign-in")
    await user.type(await screen.findByLabelText(pt.signIn.email), "ada@example.com")
    await user.type(screen.getByLabelText(pt.signIn.password), "senha-errada-1")
    await user.click(screen.getByRole("button", { name: pt.signIn.submit }))
    expect(await screen.findByRole("alert")).toHaveTextContent(pt.signIn.credentials)
    await user.clear(screen.getByLabelText(pt.signIn.password))
    await user.type(screen.getByLabelText(pt.signIn.password), "limite-limite")
    await user.click(screen.getByRole("button", { name: pt.signIn.submit }))
    expect(await screen.findByRole("alert")).toHaveTextContent(
      pt.signIn.limitedMany.replace("{minutes}", "2"),
    )
  })

  it("volta para returnTo depois do login", async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const request = input instanceof Request ? input : new Request(String(input))
        if (request.url.includes("/v1/auth/login")) {
          return json(admin, 200)
        }
        return json(admin, 200)
      }),
    )
    const router = renderAt("/sign-in?returnTo=/admin")
    await user.type(await screen.findByLabelText(pt.signIn.email), "admin@example.com")
    await user.type(screen.getByLabelText(pt.signIn.password), "correct-horse-1")
    await user.click(screen.getByRole("button", { name: pt.signIn.submit }))
    expect(
      await screen.findByRole("heading", { level: 1, name: pt.pages.admin }),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe("/admin")
  })

  it("ignora um returnTo externo", async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const request = input instanceof Request ? input : new Request(String(input))
        if (request.url.includes("/v1/me")) {
          return json(admin, 200)
        }
        return json(admin, 200)
      }),
    )
    const router = renderAt("/sign-in?returnTo=https://evil.example")
    await user.type(await screen.findByLabelText(pt.signIn.email), "admin@example.com")
    await user.type(screen.getByLabelText(pt.signIn.password), "correct-horse-1")
    await user.click(screen.getByRole("button", { name: pt.signIn.submit }))
    expect(
      await screen.findByRole("heading", { level: 1, name: pt.home.title }),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe("/")
  })

  it("pede os campos vazios em português", async () => {
    const user = userEvent.setup()
    renderAt("/sign-in")
    await user.click(await screen.findByRole("button", { name: pt.signIn.submit }))
    expect(await screen.findByText(pt.signIn.emailRequired)).toBeInTheDocument()
    expect(screen.getByText(pt.signIn.passwordRequired)).toBeInTheDocument()
  })

  it("não tem violação grave na tela de entrar", async () => {
    const { container } = render(
      <AppProviders>
        <RouterProvider
          router={createMemoryRouter(routes, { initialEntries: ["/sign-in"] })}
        />
      </AppProviders>,
    )
    await screen.findByRole("heading", { name: pt.pages.signIn })
    const results = await axe.run(container, { resultTypes: ["violations"] })
    const serious = results.violations.filter(
      (violation) => violation.impact === "serious" || violation.impact === "critical",
    )
    expect(serious.map((violation) => violation.id)).toEqual([])
  })
})

describe("guardas", () => {
  beforeEach(() => {
    queryClient.clear()
  })

  it("mostra 403 para um membro numa rota de admin", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(member, 200)))
    renderAt("/admin")
    expect(
      await screen.findByRole("heading", { name: pt.forbidden.title }),
    ).toBeInTheDocument()
    expect(screen.getByText(pt.forbidden.body)).toBeInTheDocument()
  })

  it("abre a conta de um membro", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(member, 200)))
    renderAt("/account")
    expect(
      await screen.findByRole("heading", { name: pt.pages.account }),
    ).toBeInTheDocument()
  })

  it("mostra o identificador quando o carregamento falha", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new ApiRequestError(pt.couldNotContinue, "01JREQUEST", 500)
      }),
    )
    renderAt("/account")
    expect(
      await screen.findByRole("heading", { name: pt.couldNotContinue }),
    ).toBeInTheDocument()
    expect(screen.getByText("01JREQUEST")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: pt.requestId.copy })).toBeInTheDocument()
  })
})
