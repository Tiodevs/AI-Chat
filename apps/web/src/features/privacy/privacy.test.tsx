/**
 * O Aviso de Privacidade, os Termos de Uso e o canal do titular. FR-16,
 * NFR-14, seções 10.4, 11.5, 11.7, 11.9, 11.11, 12 e 15.5 do SDD.
 *
 * As regras do canal validam e-mail, tipo e descrição de até 2.000
 * caracteres. Na tela, o Aviso lista os cinco operadores com país e
 * finalidade, explica os dois cookies e mostra a versão, o contato do
 * encarregado e as âncoras; uma pessoa sem conta envia um pedido e vê o
 * prazo; os campos vazios não enviam; o 429 mostra o limite diário; quem
 * está na conta recebe o e-mail preenchido. `installApi` troca o `fetch` por
 * uma API falsa por rota, que responde 401 ao que não conhece, como sem
 * sessão. Projeto `dom` do Vitest, com as rotas reais. Não usa a API nem
 * banco.
 */
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import axe from "axe-core"
import { createMemoryRouter, RouterProvider } from "react-router"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { AppProviders } from "@/app/providers.tsx"
import { queryClient } from "@/app/query-client.ts"
import { routes } from "@/app/router.tsx"
import { pt } from "@/i18n/pt.ts"

import { requestSchema, sentMessage } from "./model.ts"

/** Corpo de `GET /v1/legal/versions`, com o contato do encarregado. */
const versions = {
  terms: "2026-11-12.1",
  privacy_notice: "2026-11-12.1",
  privacy_contact_email: "privacidade@harborlight.example",
}

/** Um pedido que o `fetch` falso recebeu, com o caminho sem `/backend`. */
type Call = { method: string; path: string; body: unknown }

/** Resposta JSON com o `status` dado, como a API devolve. */
function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  })
}

/**
 * Troca o `fetch` por uma API falsa. Cada chave de `handlers` é
 * `MÉTODO caminho`; o que não tem tratador responde 401, como um visitante
 * sem sessão. Devolve a lista de chamadas, com o corpo JSON já lido.
 */
function installApi(handlers: Record<string, (call: Call) => Response>) {
  const calls: Call[] = []
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const request =
        input instanceof Request ? input : new Request(String(input))
      const path = new URL(request.url).pathname.replace("/backend", "")
      const text = request.method === "GET" ? "" : await request.text()
      const call = {
        method: request.method,
        path,
        body: text ? JSON.parse(text) : null,
      }
      calls.push(call)
      const handler = handlers[`${request.method} ${path}`]
      if (handler) {
        return handler(call)
      }
      return json(
        { error: { code: "unauthenticated", message: "x", request_id: "1" } },
        401,
      )
    }),
  )
  return calls
}

/**
 * Abre o app inteiro em `path`, com as rotas reais e os provedores. Devolve o
 * roteador e o resultado do `render`.
 */
function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  const view = render(
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>,
  )
  return { router, ...view }
}

beforeEach(() => {
  queryClient.clear()
})

describe("regras do canal", () => {
  it("valida e-mail, tipo e descrição", () => {
    const valid = {
      contact_email: "ana@example.com",
      request_type: "deletion",
      description: "Apaguem meus dados.",
    }
    expect(requestSchema.safeParse(valid).success).toBe(true)
    expect(
      requestSchema.safeParse({ ...valid, contact_email: "ana" }).success,
    ).toBe(false)
    expect(requestSchema.safeParse({ ...valid, request_type: "" }).success).toBe(
      false,
    )
    expect(
      requestSchema.safeParse({ ...valid, description: "x".repeat(2001) })
        .success,
    ).toBe(false)
  })

  it("mostra o prazo de resposta", () => {
    expect(sentMessage("2026-11-18T12:00:00.000Z")).toContain("2026")
  })
})

describe("Aviso de Privacidade", () => {
  it("lista os cinco operadores com país e finalidade", async () => {
    installApi({ "GET /v1/legal/versions": () => json(versions) })
    renderAt("/privacy")
    const section = await screen.findByRole("region", {
      name: pt.privacyNotice.sections.processors.title,
    })
    for (const [name, country, purpose] of pt.privacyNotice.sections.processors
      .rows) {
      const row = within(section).getByRole("row", {
        name: (accessible) => accessible.startsWith(name),
      })
      expect(row).toHaveTextContent(country)
      expect(row).toHaveTextContent(purpose)
    }
    expect(
      within(section).getAllByRole("row").map((row) => row.textContent),
    ).toHaveLength(6)
  })

  it("explica os dois cookies", async () => {
    installApi({ "GET /v1/legal/versions": () => json(versions) })
    renderAt("/privacy")
    const section = await screen.findByRole("region", {
      name: pt.privacyNotice.sections.cookies.title,
    })
    expect(
      within(section).getByRole("rowheader", { name: "atrium_session" }),
    ).toBeInTheDocument()
    expect(
      within(section).getByRole("rowheader", { name: "atrium_guest" }),
    ).toBeInTheDocument()
  })

  it("mostra a versão, o contato do encarregado e as âncoras", async () => {
    installApi({ "GET /v1/legal/versions": () => json(versions) })
    renderAt("/privacy")
    expect(
      await screen.findByText(
        pt.privacyNotice.sections.controller.contact.replace(
          "{email}",
          versions.privacy_contact_email,
        ),
      ),
    ).toBeInTheDocument()
    expect(screen.getByText(/Versão 2026-11-12.1/)).toBeInTheDocument()
    const nav = screen.getByRole("navigation", {
      name: pt.privacyNotice.contentsLabel,
    })
    expect(
      within(nav).getByRole("link", {
        name: pt.privacyNotice.sections.channel.title,
      }),
    ).toHaveAttribute("href", "#pedidos")
  })

  it("envia um pedido sem conta e mostra o prazo", async () => {
    const user = userEvent.setup()
    const calls = installApi({
      "GET /v1/legal/versions": () => json(versions),
      "POST /v1/privacy/requests": () =>
        json(
          {
            id: "00000000-0000-4000-8000-0000000000e1",
            request_type: "deletion",
            status: "open",
            received_at: "2026-11-03T12:00:00.000Z",
            due_at: "2026-11-18T12:00:00.000Z",
          },
          201,
        ),
    })
    renderAt("/privacy")
    await user.type(
      await screen.findByLabelText(pt.privacyRequest.email),
      "visitante@example.com",
    )
    await user.click(
      screen.getByRole("radio", { name: pt.privacyRequest.types.deletion }),
    )
    await user.type(
      screen.getByLabelText(pt.privacyRequest.description),
      "Quero que apaguem minha conversa.",
    )
    await user.click(
      screen.getByRole("button", { name: pt.privacyRequest.submit }),
    )
    expect(
      await screen.findByText(sentMessage("2026-11-18T12:00:00.000Z")),
    ).toBeInTheDocument()
    expect(calls.find((call) => call.method === "POST")?.body).toEqual({
      contact_email: "visitante@example.com",
      request_type: "deletion",
      description: "Quero que apaguem minha conversa.",
    })
  })

  it("pede os campos antes de enviar", async () => {
    const user = userEvent.setup()
    const calls = installApi({ "GET /v1/legal/versions": () => json(versions) })
    renderAt("/privacy")
    await user.click(
      await screen.findByRole("button", { name: pt.privacyRequest.submit }),
    )
    expect(
      await screen.findByText(pt.privacyRequest.emailInvalid),
    ).toBeInTheDocument()
    expect(screen.getByText(pt.privacyRequest.typeRequired)).toBeInTheDocument()
    expect(
      screen.getByText(pt.privacyRequest.descriptionRequired),
    ).toBeInTheDocument()
    expect(calls.some((call) => call.method === "POST")).toBe(false)
  })

  it("mostra o limite diário do canal", async () => {
    const user = userEvent.setup()
    installApi({
      "GET /v1/legal/versions": () => json(versions),
      "POST /v1/privacy/requests": () =>
        json(
          {
            error: {
              code: "rate_limited",
              message: "Você fez muitos pedidos hoje. Tente de novo amanhã.",
              request_id: "01DSR",
              retry_after_seconds: 3600,
            },
          },
          429,
        ),
    })
    renderAt("/privacy")
    await user.type(
      await screen.findByLabelText(pt.privacyRequest.email),
      "visitante@example.com",
    )
    await user.click(
      screen.getByRole("radio", { name: pt.privacyRequest.types.other }),
    )
    await user.type(screen.getByLabelText(pt.privacyRequest.description), "Oi")
    await user.click(
      screen.getByRole("button", { name: pt.privacyRequest.submit }),
    )
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Você fez muitos pedidos hoje. Tente de novo amanhã.",
    )
  })

  it("preenche o e-mail de quem está na conta", async () => {
    installApi({
      "GET /v1/legal/versions": () => json(versions),
      "GET /v1/me": () =>
        json({
          id: "00000000-0000-0000-0000-000000000002",
          email: "ana@example.com",
          full_name: "Ana",
          phone: null,
          visitor_type: null,
          visit_reason: null,
          role: "member",
          needs_legal_acceptance: false,
        }),
    })
    renderAt("/privacy")
    await waitFor(() =>
      expect(screen.getByLabelText(pt.privacyRequest.email)).toHaveValue(
        "ana@example.com",
      ),
    )
  })

  it("não tem violação grave no Aviso nem nos Termos", async () => {
    installApi({ "GET /v1/legal/versions": () => json(versions) })
    const { container, unmount } = renderAt("/privacy")
    await screen.findByLabelText(pt.privacyRequest.email)
    const notice = await axe.run(container, { resultTypes: ["violations"] })
    unmount()
    const terms = renderAt("/terms")
    await screen.findByRole("heading", { name: pt.termsOfUse.sections[0].title })
    const termsResult = await axe.run(terms.container, {
      resultTypes: ["violations"],
    })
    const serious = [...notice.violations, ...termsResult.violations].filter(
      (violation) =>
        violation.impact === "serious" || violation.impact === "critical",
    )
    expect(serious.map((violation) => violation.id)).toEqual([])
  })
})

describe("Termos de Uso", () => {
  it("mostra as seções e a versão", async () => {
    installApi({ "GET /v1/legal/versions": () => json(versions) })
    renderAt("/terms")
    for (const section of pt.termsOfUse.sections) {
      expect(
        await screen.findByRole("heading", { level: 2, name: section.title }),
      ).toBeInTheDocument()
    }
    expect(screen.getByText(/Versão 2026-11-12.1/)).toBeInTheDocument()
  })
})
