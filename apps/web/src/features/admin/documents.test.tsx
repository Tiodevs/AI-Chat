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
  displayStatus,
  fileProblem,
  isProcessing,
  maxUploadBytes,
  type AdminDocument,
} from "./documents-model.ts"

const t = pt.documents

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

function version(
  number: number,
  status: "processing" | "ready" | "failed",
  error: string | null = null,
) {
  return {
    id: `00000000-0000-4000-8000-00000000000${String(number)}`,
    version: number,
    filename: "04-parking.md",
    media_type: "text/markdown",
    byte_size: 120,
    ingestion_status: status,
    error,
    created_at: "2026-11-04T10:00:00Z",
  }
}

function doc(
  id: string,
  title: string,
  overrides: Partial<AdminDocument> = {},
): AdminDocument {
  return {
    id,
    title,
    slug: title.toLowerCase().replaceAll(" ", "-"),
    status: "active",
    created_at: "2026-11-04T10:00:00Z",
    updated_at: "2026-11-04T10:05:00Z",
    active_version: version(1, "ready"),
    latest_version: version(1, "ready"),
    ...overrides,
  }
}

const parking = doc("00000000-0000-4000-8000-000000000101", "Estacionamento", {
  latest_version: version(2, "processing"),
})
const visiting = doc("00000000-0000-4000-8000-000000000102", "Visitas", {
  latest_version: version(2, "failed", "Não foi possível embedar o documento."),
})
const cafe = doc("00000000-0000-4000-8000-000000000103", "Lanchonete")
const archived = doc("00000000-0000-4000-8000-000000000104", "Antigo", {
  status: "archived",
})

type Call = { method: string; path: string; body: string }

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  })
}

function installApi(
  documents: AdminDocument[],
  handlers: Record<string, (call: Call) => Response> = {},
) {
  const calls: Call[] = []
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const request = input instanceof Request ? input : new Request(String(input))
      const path = new URL(request.url).pathname.replace("/backend", "")
      // O formData() do jsdom não termina com corpo multipart; o texto basta.
      const call = {
        method: request.method,
        path,
        body: request.method === "GET" ? "" : await request.text(),
      }
      calls.push(call)
      if (path === "/v1/me") {
        return json(admin)
      }
      const handler = handlers[`${request.method} ${path}`]
      if (handler) {
        return handler(call)
      }
      if (request.method === "GET" && path === "/v1/admin/documents") {
        return json({ documents })
      }
      return json({ error: { code: "not_found", message: "x", request_id: "r-1" } }, 404)
    }),
  )
  return calls
}

/** O undici do jsdom serializa o File como "blob"; o append mostra o que o navegador envia. */
function spyFormData() {
  return vi.spyOn(FormData.prototype, "append")
}

function appendedFile(spy: ReturnType<typeof spyFormData>) {
  const call = spy.mock.calls.find(([key]) => key === "file")
  return call?.[2]
}

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  return render(
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>,
  )
}

async function table(title = "") {
  const found = await screen.findByRole("table", { name: t.table.caption })
  if (title) {
    await within(found).findByRole("rowheader", { name: new RegExp(title) })
  }
  return found
}

beforeEach(() => {
  queryClient.clear()
})

describe("regras dos documentos", () => {
  it("deriva o status da versão mais nova e do arquivamento", () => {
    expect(displayStatus(parking)).toBe("processing")
    expect(displayStatus(visiting)).toBe("failed")
    expect(displayStatus(cafe)).toBe("ready")
    expect(displayStatus(archived)).toBe("archived")
    expect(isProcessing([cafe, parking])).toBe(true)
    expect(isProcessing([cafe, visiting])).toBe(false)
  })

  it("adianta no navegador o limite de 10 MB e os tipos aceitos (FR-10)", () => {
    expect(fileProblem(null)).toBe(t.dropzone.required)
    expect(fileProblem(new File(["x"], "contrato.docx"))).toBe(t.dropzone.wrongType)
    const big = new File(["x"], "grande.pdf")
    Object.defineProperty(big, "size", { value: maxUploadBytes + 1 })
    expect(fileProblem(big)).toBe(t.dropzone.tooLarge)
    expect(fileProblem(new File(["# A"], "guia.MD"))).toBeNull()
  })
})

describe("tela de documentos", () => {
  it("lista título, versão ativa, status e as ações de cada estado", async () => {
    installApi([parking, visiting, cafe, archived])
    renderAt("/admin/documents")
    const rows = within(await table("Antigo")).getAllByRole("row")
    expect(rows).toHaveLength(5)

    const processing = within(await table()).getByRole("row", { name: /Estacionamento/ })
    expect(processing).toHaveTextContent(t.status.processing)
    expect(processing).toHaveTextContent("v1")
    expect(processing).toHaveTextContent(t.processingNote.replace("{version}", "2"))
    expect(
      within(processing).getByRole("button", { name: `${t.actions.replace}: Estacionamento` }),
    ).toBeDisabled()

    const failed = within(await table()).getByRole("row", { name: /Visitas/ })
    expect(failed).toHaveTextContent(t.status.failed)
    expect(failed).toHaveTextContent("Não foi possível embedar o documento.")
    expect(
      within(failed).getByRole("button", { name: `${t.actions.retry}: Visitas` }),
    ).toBeEnabled()

    const old = within(await table()).getByRole("row", { name: /Antigo/ })
    expect(old).toHaveTextContent(t.status.archived)
    expect(within(old).queryAllByRole("button")).toHaveLength(0)
  })

  it("mostra a barra lateral com Operação e Sistema para o admin", async () => {
    installApi([])
    renderAt("/admin/documents")
    await screen.findByText(t.table.empty)
    // A barra lateral carrega sob demanda e pode chegar depois da tabela.
    const nav = await screen.findByRole("navigation", { name: pt.sidebar.label })
    expect(within(nav).getByText(pt.nav.operations)).toBeInTheDocument()
    expect(within(nav).getByText(pt.nav.system)).toBeInTheDocument()
    expect(within(nav).getByRole("link", { name: pt.nav.documents })).toHaveAttribute(
      "aria-current",
      "page",
    )
  })

  it("recusa no navegador um tipo não aceito sem chamar a API", async () => {
    const calls = installApi([])
    const user = userEvent.setup({ applyAccept: false })
    renderAt("/admin/documents")
    await screen.findByText(t.table.empty)
    await user.upload(screen.getByLabelText(t.dropzone.label), new File(["x"], "contrato.docx"))
    await user.click(screen.getByRole("button", { name: t.upload.submit }))
    expect(await screen.findByText(t.dropzone.wrongType)).toBeInTheDocument()
    expect(calls.some((call) => call.method === "POST")).toBe(false)
  })

  it("envia o arquivo e o título em multipart e anuncia o envio", async () => {
    const calls = installApi([], {
      "POST /v1/admin/documents": () =>
        json({ ...parking, title: "Guia", active_version: null }, 201),
    })
    const append = spyFormData()
    const user = userEvent.setup()
    renderAt("/admin/documents")
    await screen.findByText(t.table.empty)
    await user.upload(
      screen.getByLabelText(t.dropzone.label),
      new File(["# Guia"], "guia.md", { type: "text/markdown" }),
    )
    await user.type(screen.getByLabelText(t.upload.titleLabel), "Guia")
    await user.click(screen.getByRole("button", { name: t.upload.submit }))
    expect(
      await screen.findByText(t.upload.sent.replace("{title}", "Guia")),
    ).toBeInTheDocument()
    const sent = calls.find((call) => call.method === "POST")
    expect(sent?.path).toBe("/v1/admin/documents")
    expect(sent?.body).toContain('name="title"')
    expect(sent?.body).toContain("Guia")
    expect(sent?.body).toContain('name="file"')
    expect(appendedFile(append)).toBe("guia.md")
    append.mockRestore()
  })

  it("mostra o erro de campo que o servidor devolve (NFR-10)", async () => {
    installApi([], {
      "POST /v1/admin/documents": () =>
        json(
          {
            error: {
              code: "validation_error",
              message: "Não foi possível enviar o arquivo.",
              request_id: "r-2",
              field_errors: { file: "O arquivo passa de 10 MB." },
            },
          },
          422,
        ),
    })
    const user = userEvent.setup()
    renderAt("/admin/documents")
    await screen.findByText(t.table.empty)
    await user.upload(screen.getByLabelText(t.dropzone.label), new File(["# A"], "a.md"))
    await user.click(screen.getByRole("button", { name: t.upload.submit }))
    expect(await screen.findByText("O arquivo passa de 10 MB.")).toBeInTheDocument()
    expect(screen.getByLabelText(t.dropzone.label)).toHaveAttribute("aria-invalid", "true")
  })

  it("substitui pelo Sheet, com título e a promessa da versão ativa", async () => {
    const calls = installApi([cafe], {
      [`POST /v1/admin/documents/${cafe.id}/replace`]: () =>
        json({ ...cafe, latest_version: version(2, "processing") }, 202),
    })
    const append = spyFormData()
    const user = userEvent.setup()
    renderAt("/admin/documents")
    await table("Lanchonete")
    await user.click(screen.getByRole("button", { name: `${t.actions.replace}: Lanchonete` }))
    const sheet = await screen.findByRole("dialog", { name: t.replace.title })
    expect(sheet).toHaveTextContent(t.replace.description.replace("{title}", "Lanchonete"))
    await user.upload(within(sheet).getByLabelText(t.dropzone.label), new File(["# L"], "l.md"))
    await user.click(within(sheet).getByRole("button", { name: t.replace.submit }))
    expect(
      await screen.findByText(t.replace.sent.replace("{title}", "Lanchonete")),
    ).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    })
    const sent = calls.find((call) => call.method === "POST")
    expect(sent?.path).toBe(`/v1/admin/documents/${cafe.id}/replace`)
    expect(sent?.body).toContain('name="file"')
    expect(appendedFile(append)).toBe("l.md")
    append.mockRestore()
  })

  it("tenta de novo uma versão que falhou", async () => {
    const calls = installApi([visiting], {
      [`POST /v1/admin/documents/${visiting.id}/retry`]: () =>
        json({ ...visiting, latest_version: version(3, "processing") }, 202),
    })
    const user = userEvent.setup()
    renderAt("/admin/documents")
    await table("Visitas")
    await user.click(screen.getByRole("button", { name: `${t.actions.retry}: Visitas` }))
    expect(
      await screen.findByText(t.actions.retried.replace("{title}", "Visitas")),
    ).toBeInTheDocument()
    expect(calls.map((call) => `${call.method} ${call.path}`)).toContain(
      `POST /v1/admin/documents/${visiting.id}/retry`,
    )
  })

  it("arquiva depois da confirmação", async () => {
    const calls = installApi([cafe], {
      [`POST /v1/admin/documents/${cafe.id}/archive`]: () =>
        json({ ...cafe, status: "archived" }),
    })
    const user = userEvent.setup()
    renderAt("/admin/documents")
    await table("Lanchonete")
    await user.click(screen.getByRole("button", { name: `${t.actions.archive}: Lanchonete` }))
    const dialog = await screen.findByRole("alertdialog", {
      name: t.actions.archiveTitle.replace("{title}", "Lanchonete"),
    })
    expect(calls.some((call) => call.method === "POST")).toBe(false)
    await user.click(within(dialog).getByRole("button", { name: t.actions.archiveConfirm }))
    expect(
      await screen.findByText(t.actions.archived.replace("{title}", "Lanchonete")),
    ).toBeInTheDocument()
    expect(calls.map((call) => `${call.method} ${call.path}`)).toContain(
      `POST /v1/admin/documents/${cafe.id}/archive`,
    )
  })

  it("passa no axe sem violação séria", async () => {
    installApi([parking, visiting, cafe, archived])
    const { container } = renderAt("/admin/documents")
    await table("Antigo")
    const result = await axe.run(container, { resultTypes: ["violations"] })
    const serious = result.violations.filter(
      (violation) => violation.impact === "serious" || violation.impact === "critical",
    )
    expect(serious.map((violation) => violation.id)).toEqual([])
  })
})
