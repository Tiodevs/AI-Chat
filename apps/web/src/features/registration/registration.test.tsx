/**
 * As telas do cadastro por conversa (`/register`) e por formulário
 * (`/register/form`). FR-5, FR-6, FR-8, NFR-14, seções 7.2, 8.5, 12, 15.3
 * (J4), 15.5, 16.3 (M12), 16.6 e 21.1 do SDD.
 *
 * Prova que o cartão de resumo mostra os campos de cada turno, que o e-mail
 * já usado oferece entrar, que uma dúvida fica no chat, que o modelo
 * indisponível avisa sem sair da tela, que o foco chega à senha depois de
 * M12 com e sem redução de movimento, que o `ConsentFieldSet` exige os
 * obrigatórios e destaca a personalização, que o formulário mostra o erro de
 * campo do servidor e chega do chat com a senha vazia, e que Usar o
 * formulário espera o turno a caminho (J4). Cada teste troca o `fetch` por
 * uma API falsa que monta as respostas de sessão com `session`. Projeto
 * `dom` do Vitest, com as rotas reais. Não usa a API nem banco.
 */
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
/** Versão vigente dos Termos e do Aviso, a de `GET /v1/legal/versions`. */
const version = "2026-11-12.1"
/** A frase que a API manda quando o e-mail já tem conta (seção 8.5). */
const taken = "Este e-mail já tem uma conta. Entre para continuar."

/** Os campos entendidos de uma sessão, como em `fields` da seção 12. */
type Fields = {
  full_name: string | null
  email: string | null
  phone: string | null
  visitor_type: string | null
  visit_reason: string | null
}

/** Nenhum campo entendido ainda. */
const emptyFields: Fields = {
  full_name: null,
  email: null,
  phone: null,
  visitor_type: null,
  visit_reason: null,
}

/** Resposta JSON com o `status` dado, como a API devolve. */
function json(body: unknown, status: number) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  })
}

/**
 * Corpo de uma sessão de cadastro por chat, no formato da seção 12: os
 * campos entendidos, os erros de campo, o `next_step` e a transcrição. O
 * `prompt` é a última fala, e o `status` padrão é `collecting_required`.
 */
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

/**
 * Envelope de erro da seção 12 com `field_errors`: `conflict` no 409 e
 * `validation_error` nos outros status.
 */
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

/**
 * Abre o app inteiro em `path`, com as rotas reais e os provedores. Devolve o
 * roteador e o resultado do `render`.
 */
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
    const toggle = await screen.findByRole("button", {
      name: pt.registration.summaryShow.replace("{count}", "0"),
    })
    expect(toggle).toHaveAttribute("aria-expanded", "false")
    expect(
      screen.queryByRole("region", { name: pt.registration.summaryTitle })
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole("list", { name: pt.registration.stepsLabel })
    ).not.toBeInTheDocument()
    await user.click(toggle)
    expect(
      screen.getByRole("button", { name: pt.registration.summaryHide })
    ).toHaveAttribute("aria-expanded", "true")
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
    const thread = await screen.findByRole("region", {
      name: pt.registration.thread,
    })
    expect((await within(thread).findAllByText(taken)).length).toBeGreaterThan(0)
    expect(
      within(thread).getByRole("link", { name: pt.registration.signIn })
    ).toHaveAttribute("href", "/sign-in")
    await user.click(
      screen.getByRole("button", {
        name: pt.registration.summaryShow.replace("{count}", "1"),
      })
    )
    const summary = await screen.findByRole("region", {
      name: pt.registration.summaryTitle,
    })
    expect(await within(summary).findByRole("alert")).toHaveTextContent(taken)
    expect(
      within(summary).getByRole("link", { name: pt.registration.signIn })
    ).toHaveAttribute("href", "/sign-in")
  })

  it("uma dúvida permanece no chat e recebe outra resposta", async () => {
    const user = userEvent.setup()
    const reply = "Use um e-mail que você abre todo dia. Qual é o seu e-mail?"
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
              fields: { full_name: "Felipe Santos" },
              nextStep: "email",
              messages: [{ role: "assistant", text: "Qual é o seu e-mail?" }],
            }),
            201
          )
        }
        if (path.endsWith("/messages")) {
          return json(
            session({
              fields: { full_name: "Felipe Santos" },
              nextStep: "email",
              messages: [
                { role: "assistant", text: "Qual é o seu e-mail?" },
                { role: "user", text: "O que seria o melhor email?" },
                { role: "assistant", text: reply },
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
      "O que seria o melhor email?"
    )
    await user.click(screen.getByRole("button", { name: pt.registration.send }))
    expect(await screen.findAllByText(reply)).toHaveLength(2)
    expect(router.state.location.pathname).toBe("/register")
    expect(
      screen.getByRole("link", { name: pt.registration.useForm })
    ).toBeInTheDocument()
  })

  it("com o modelo indisponível, o chat avisa e não sai da tela", async () => {
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
    const field = await screen.findByLabelText(pt.registration.messageLabel)
    await user.type(field, "Ana")
    await user.click(screen.getByRole("button", { name: pt.registration.send }))
    const alert = await screen.findByRole("alert")
    expect(
      within(alert).getByText(pt.registration.unavailable)
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe("/register")
    expect(field).toHaveValue("Ana")
    expect(
      within(alert).getByRole("button", { name: pt.registration.retry })
    ).toBeInTheDocument()
    expect(
      within(alert).getByRole("link", { name: pt.registration.useForm })
    ).toHaveAttribute("href", `/register/form?session=${sessionId}`)
    await user.click(
      within(alert).getByRole("button", { name: pt.registration.dismiss })
    )
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("o foco chega à senha com movimento reduzido", async () => {
    installPasswordStep()
    renderAt("/register")
    const input = await screen.findByLabelText(pt.registration.fields.password)
    await waitFor(() => expect(input).toHaveFocus())
  })

  it("o foco chega à senha quando M12 termina com movimento ligado", async () => {
    // A preferência "off" desliga o movimento reduzido, mesmo com o sistema
    // pedindo redução. O `gsap.fromTo` falso chama o `onComplete` na hora,
    // que é onde M12 entrega o foco.
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

  it("Usar o formulário com a mensagem a caminho espera o turno e leva o nome (J4)", async () => {
    const user = userEvent.setup()
    const greeting = "Olá. Eu sou o Atrium. Qual é o seu nome completo?"
    // O `POST` da mensagem espera `turn`, que o teste solta depois de clicar
    // em Usar o formulário: assim a mensagem fica a caminho durante o clique.
    let processed = false
    let release: () => void = () => undefined
    const turn = new Promise<void>((resolve) => {
      release = resolve
    })
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const request = input instanceof Request ? input : new Request(String(input))
        const path = new URL(request.url).pathname
        if (path.endsWith("/v1/legal/versions")) {
          return json({ terms: version, privacy_notice: version }, 200)
        }
        if (request.method === "POST" && path.endsWith("/v1/registration/sessions")) {
          return json(
            session({ nextStep: "full_name", messages: [{ role: "assistant", text: greeting }] }),
            201,
          )
        }
        if (request.method === "POST" && path.endsWith("/messages")) {
          await turn
          processed = true
          return json(
            session({
              fields: { full_name: "Ana Costa" },
              nextStep: "email",
              messages: [
                { role: "assistant", text: greeting },
                { role: "user", text: "Ana Costa" },
                { role: "assistant", text: "Qual é o seu e-mail?" },
              ],
            }),
            200,
          )
        }
        if (request.method === "GET" && path.includes("/sessions/")) {
          return json(
            session({
              fields: processed ? { full_name: "Ana Costa" } : {},
              nextStep: processed ? "email" : "full_name",
              messages: [{ role: "assistant", text: greeting }],
            }),
            200,
          )
        }
        return json({ error: { code: "unauthenticated", message: "Entre", request_id: "01" } }, 401)
      }),
    )
    const { router } = renderAt("/register")
    await user.type(await screen.findByLabelText(pt.registration.messageLabel), "Ana Costa")
    await user.click(screen.getByRole("button", { name: pt.registration.send }))
    await user.click(screen.getByRole("link", { name: pt.registration.useForm }))
    // Com a mensagem a caminho, o link espera: o formulário ainda não abriu.
    expect(router.state.location.pathname).toBe("/register")

    release()
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/register/form")
    })
    expect(router.state.location.search).toContain(sessionId)
    expect(await screen.findByLabelText(pt.registration.fields.full_name)).toHaveValue("Ana Costa")
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

/**
 * Troca o `fetch` por uma API falsa cuja sessão nova já começa no passo da
 * senha (`next_step` `password`), com nome e e-mail entendidos.
 */
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

/** Os ids das violações sérias e críticas de um resultado do axe. */
function serious(results: axe.AxeResults) {
  return results.violations
    .filter(
      (violation) =>
        violation.impact === "serious" || violation.impact === "critical"
    )
    .map((violation) => violation.id)
}
