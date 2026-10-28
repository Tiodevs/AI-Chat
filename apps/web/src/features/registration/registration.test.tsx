import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import axe from "axe-core"
import { createMemoryRouter, RouterProvider } from "react-router"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { AppProviders } from "@/app/providers.tsx"
import { routes } from "@/app/router.tsx"
import { ConsentFieldSet } from "@/components/patterns/consent-field-set.tsx"
import { pt } from "@/i18n/pt.ts"
import { gsap } from "@/motion/gsap.ts"

import { consentIssues, emptyConsents } from "./model.ts"

const sessionId = "00000000-0000-4000-8000-0000000000f1"
const version = "2026-10-25.1"
const taken = "Este e-mail já tem uma conta. Entre para continuar."

type Fields = {
  full_name: string | null
  email: string | null
  phone: string | null
  visitor_type: string | null
  visit_reason: string | null
}

const emptyFields: Fields = {
  full_name: null,
  email: null,
  phone: null,
  visitor_type: null,
  visit_reason: null,
}

function json(body: unknown, status: number) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  })
}

function session(input: {
  fields?: Partial<Fields>
  fieldErrors?: Record<string, string>
  nextStep: string
  messages: Array<{ role: "user" | "assistant"; text: string }>
  status?: string
}) {
  return {
    id: sessionId,
    status: input.status ?? "collecting_required",
    path: "chat",
    fields: { ...emptyFields, ...input.fields },
    field_errors: input.fieldErrors ?? {},
    next_step: input.nextStep,
    prompt: input.messages.at(-1)?.text ?? "",
    messages: input.messages.map((message, index) => ({
      ...message,
      created_at: `2026-10-28T00:00:0${index}.000Z`,
    })),
    expires_at: "2026-10-29T00:00:00.000Z",
  }
}

function errorBody(
  message: string,
  fieldErrors?: Record<string, string>,
  status = 422
) {
  return json(
    {
      error: {
        code: status === 409 ? "conflict" : "validation_error",
        message,
        request_id: "01REG",
        field_errors: fieldErrors,
      },
    },
    status
  )
}

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  const view = render(
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  )
  return { router, ...view }
}

describe("telas do cadastro", () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  it("o cartão mostra os campos entendidos em cada turno", async () => {
    const user = userEvent.setup()
    const greeting = "Olá. Eu sou o Atrium. Qual é o seu nome completo?"
    let fields: Fields = { ...emptyFields }
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const request =
          input instanceof Request ? input : new Request(String(input))
        const path = new URL(request.url).pathname
        if (path.endsWith("/v1/legal/versions")) {
          return json({ terms: version, privacy_notice: version }, 200)
        }
        if (
          request.method === "POST" &&
          path.endsWith("/v1/registration/sessions")
        ) {
          return json(
            session({
              nextStep: "full_name",
              messages: [{ role: "assistant", text: greeting }],
            }),
            201
          )
        }
        if (path.endsWith("/messages")) {
          const body = (await request.json()) as { text: string }
          const messages = [
            { role: "assistant" as const, text: greeting },
            { role: "user" as const, text: body.text },
          ]
          if (!fields.full_name) {
            fields = { ...fields, full_name: body.text }
            messages.push({ role: "assistant", text: "Qual é o seu e-mail?" })
            return json(
              session({
                fields,
                nextStep: "email",
                messages,
              }),
              200
            )
          }
          fields = { ...fields, email: body.text }
          messages.push({ role: "assistant", text: "Qual é o seu telefone?" })
          return json(
            session({
              fields,
              nextStep: "phone",
              status: "collecting_optional",
              messages,
            }),
            200
          )
        }
        return json(
          {
            error: {
              code: "unauthenticated",
              message: "Entre",
              request_id: "01",
            },
          },
          401
        )
      })
    )

    renderAt("/register")
    const summary = await screen.findByRole("region", {
      name: pt.registration.summaryTitle,
    })
    await user.type(
      await screen.findByLabelText(pt.registration.messageLabel),
      "Ana Costa"
    )
    await user.click(screen.getByRole("button", { name: pt.registration.send }))
    expect(await within(summary).findByText("Ana Costa")).toBeInTheDocument()
    expect(
      within(summary).getAllByText(pt.registration.summaryEmpty).length
    ).toBeGreaterThan(0)

    await user.type(
      screen.getByLabelText(pt.registration.messageLabel),
      "ana@example.com"
    )
    await user.click(screen.getByRole("button", { name: pt.registration.send }))
    expect(
      await within(summary).findByText("ana@example.com")
    ).toBeInTheDocument()
    expect(within(summary).getByText("Ana Costa")).toBeInTheDocument()
  })

  it("oferece entrar quando o e-mail já tem conta", async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const request =
          input instanceof Request ? input : new Request(String(input))
        const path = new URL(request.url).pathname
        if (path.endsWith("/v1/legal/versions")) {
          return json({ terms: version, privacy_notice: version }, 200)
        }
        if (request.method === "POST" && path.endsWith("/sessions")) {
          return json(
            session({
              fields: { full_name: "Ana Costa" },
              nextStep: "email",
              messages: [{ role: "assistant", text: "Qual é o seu e-mail?" }],
            }),
            201
          )
        }
        if (path.endsWith("/messages")) {
          return json(
            session({
              fields: { full_name: "Ana Costa" },
              fieldErrors: { email: taken },
              nextStep: "email",
              messages: [
                { role: "assistant", text: "Qual é o seu e-mail?" },
                { role: "user", text: "ana@example.com" },
                { role: "assistant", text: taken },
              ],
            }),
            200
          )
        }
        return json(
          {
            error: {
              code: "unauthenticated",
              message: "Entre",
              request_id: "01",
            },
          },
          401
        )
      })
    )
    renderAt("/register")
    await user.type(
      await screen.findByLabelText(pt.registration.messageLabel),
      "ana@example.com"
    )
    await user.click(screen.getByRole("button", { name: pt.registration.send }))
    const summary = await screen.findByRole("region", {
      name: pt.registration.summaryTitle,
    })
    expect(await within(summary).findByRole("alert")).toHaveTextContent(taken)
    expect(
      within(summary).getByRole("link", { name: pt.registration.signIn })
    ).toHaveAttribute("href", "/sign-in")
  })

  it("com o modelo indisponível, o chat abre o formulário", async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const request =
          input instanceof Request ? input : new Request(String(input))
        const path = new URL(request.url).pathname
        if (path.endsWith("/v1/legal/versions")) {
          return json({ terms: version, privacy_notice: version }, 200)
        }
        if (request.method === "POST" && path.endsWith("/sessions")) {
          return json(
            session({
              nextStep: "full_name",
              messages: [
                { role: "assistant", text: "Qual é o seu nome completo?" },
              ],
            }),
            201
          )
        }
        if (path.endsWith("/messages")) {
          return errorBody(pt.registration.unavailable, undefined, 503)
        }
        if (request.method === "GET" && path.includes("/sessions/")) {
          return json(
            session({
              nextStep: "full_name",
              messages: [
                { role: "assistant", text: "Qual é o seu nome completo?" },
              ],
            }),
            200
          )
        }
        return json(
          {
            error: {
              code: "unauthenticated",
              message: "Entre",
              request_id: "01",
            },
          },
          401
        )
      })
    )
    const { router } = renderAt("/register")
    await user.type(
      await screen.findByLabelText(pt.registration.messageLabel),
      "Ana"
    )
    await user.click(screen.getByRole("button", { name: pt.registration.send }))
    expect(
      await screen.findByRole("heading", { name: pt.pages.registerForm })
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe("/register/form")
    expect(router.state.location.search).toContain("unavailable=1")
    expect(router.state.location.search).toContain(`session=${sessionId}`)
    expect(screen.getByText(pt.registration.unavailable)).toBeInTheDocument()
  })

  it("o foco chega à senha com movimento reduzido", async () => {
    installPasswordStep()
    renderAt("/register")
    const input = await screen.findByLabelText(pt.registration.fields.password)
    await waitFor(() => expect(input).toHaveFocus())
  })

  it("o foco chega à senha quando M12 termina com movimento ligado", async () => {
    localStorage.setItem("atrium.motion-preference", "off")
    const fromTo = vi
      .spyOn(gsap, "fromTo")
      .mockImplementation((...args: unknown[]) => {
        const vars = args[2] as { onComplete?: () => void } | undefined
        vars?.onComplete?.()
        return {
          kill() {
            return undefined
          },
        } as unknown as ReturnType<typeof gsap.fromTo>
      })
    try {
      installPasswordStep()
      renderAt("/register")
      const input = await screen.findByLabelText(
        pt.registration.fields.password
      )
      await waitFor(() => expect(input).toHaveFocus())
    } finally {
      fromTo.mockRestore()
    }
  })

  it("o ConsentFieldSet exige os obrigatórios e destaca a personalização", async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(
      <AppProviders>
        <RouterProvider
          router={createMemoryRouter([
            {
              path: "/",
              element: (
                <ConsentFieldSet
                  value={emptyConsents()}
                  onChange={onChange}
                  errors={consentIssues(emptyConsents())}
                  disabled={false}
                />
              ),
            },
          ])}
        />
      </AppProviders>
    )
    const personalization = screen.getByRole("checkbox", {
      name: pt.registration.personalization,
    })
    const quality = screen.getByRole("checkbox", {
      name: pt.registration.quality,
    })
    expect(personalization).not.toBeChecked()
    expect(quality).not.toBeChecked()
    expect(
      screen.getByRole("checkbox", { name: pt.registration.terms })
    ).toHaveAttribute("aria-invalid", "true")
    expect(
      screen.getByRole("checkbox", { name: pt.registration.age })
    ).toHaveAttribute("aria-invalid", "true")
    const highlighted = document.querySelector(
      "[data-highlighted='personalization']"
    )
    expect(highlighted).toHaveTextContent(pt.registration.personalizationNote)
    expect(highlighted).toHaveTextContent(pt.registration.personalizationBadge)
    await user.click(personalization)
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        profile_personalization: true,
        quality_improvement: false,
      })
    )
  })

  it("o formulário mostra o erro de campo do servidor", async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const request =
          input instanceof Request ? input : new Request(String(input))
        const path = new URL(request.url).pathname
        if (path.endsWith("/v1/legal/versions")) {
          return json({ terms: version, privacy_notice: version }, 200)
        }
        if (path.endsWith("/v1/registration/form")) {
          return errorBody(
            "Não foi possível concluir o cadastro.",
            { email: taken },
            409
          )
        }
        return json(
          {
            error: {
              code: "unauthenticated",
              message: "Entre",
              request_id: "01",
            },
          },
          401
        )
      })
    )
    renderAt("/register/form")
    const form = await screen.findByRole("form", {
      name: pt.pages.registerForm,
    })
    await user.type(
      within(form).getByLabelText(pt.registration.fields.full_name),
      "Ana Costa"
    )
    await user.type(
      within(form).getByLabelText(pt.registration.fields.email),
      "ana@example.com"
    )
    await user.type(
      within(form).getByLabelText(pt.registration.fields.password),
      "senha-segura-1"
    )
    await user.click(
      within(form).getByRole("checkbox", { name: pt.registration.terms })
    )
    await user.click(
      within(form).getByRole("checkbox", { name: pt.registration.age })
    )
    await user.click(
      within(form).getByRole("button", { name: pt.registration.createAccount })
    )
    expect(await within(form).findByText(taken)).toBeInTheDocument()
    expect(
      within(form).getByRole("link", { name: pt.registration.signIn })
    ).toHaveAttribute("href", "/sign-in")
  })

  it("o formulário preenche o chat e deixa a senha vazia", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const request =
          input instanceof Request ? input : new Request(String(input))
        const path = new URL(request.url).pathname
        if (path.endsWith("/v1/legal/versions")) {
          return json({ terms: version, privacy_notice: version }, 200)
        }
        if (request.method === "GET" && path.includes("/sessions/")) {
          return json(
            session({
              fields: { full_name: "Ana Costa", email: "ana@example.com" },
              nextStep: "phone",
              messages: [{ role: "assistant", text: "Qual é o seu telefone?" }],
            }),
            200
          )
        }
        return json(
          {
            error: {
              code: "unauthenticated",
              message: "Entre",
              request_id: "01",
            },
          },
          401
        )
      })
    )
    renderAt(`/register/form?session=${sessionId}`)
    expect(
      await screen.findByLabelText(pt.registration.fields.full_name)
    ).toHaveValue("Ana Costa")
    expect(screen.getByLabelText(pt.registration.fields.email)).toHaveValue(
      "ana@example.com"
    )
    expect(screen.getByLabelText(pt.registration.fields.password)).toHaveValue(
      ""
    )
    expect(
      screen.getByRole("checkbox", { name: pt.registration.personalization })
    ).not.toBeChecked()
    expect(
      screen.getByRole("checkbox", { name: pt.registration.quality })
    ).not.toBeChecked()
  })

  it("não tem violação grave nas telas de cadastro", async () => {
    installPasswordStep()
    const registered = renderAt("/register")
    await screen.findByLabelText(pt.registration.fields.password)
    const first = await axe.run(registered.container, {
      resultTypes: ["violations"],
    })
    expect(serious(first)).toEqual([])
    registered.unmount()

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const request =
          input instanceof Request ? input : new Request(String(input))
        if (new URL(request.url).pathname.endsWith("/v1/legal/versions")) {
          return json({ terms: version, privacy_notice: version }, 200)
        }
        return json(
          {
            error: {
              code: "unauthenticated",
              message: "Entre",
              request_id: "01",
            },
          },
          401
        )
      })
    )
    const form = renderAt("/register/form")
    await screen.findByRole("form", { name: pt.pages.registerForm })
    const second = await axe.run(form.container, {
      resultTypes: ["violations"],
    })
    expect(serious(second)).toEqual([])
  })
})

function installPasswordStep() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const request =
        input instanceof Request ? input : new Request(String(input))
      const path = new URL(request.url).pathname
      if (path.endsWith("/v1/legal/versions")) {
        return json({ terms: version, privacy_notice: version }, 200)
      }
      if (request.method === "POST" && path.endsWith("/sessions")) {
        return json(
          session({
            fields: { full_name: "Ana Costa", email: "ana@example.com" },
            nextStep: "password",
            status: "awaiting_password",
            messages: [
              { role: "assistant", text: pt.registration.passwordNote },
            ],
          }),
          201
        )
      }
      return json(
        {
          error: {
            code: "unauthenticated",
            message: "Entre",
            request_id: "01",
          },
        },
        401
      )
    })
  )
}

function serious(results: axe.AxeResults) {
  return results.violations
    .filter(
      (violation) =>
        violation.impact === "serious" || violation.impact === "critical"
    )
    .map((violation) => violation.id)
}
