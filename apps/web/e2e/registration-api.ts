/**
 * Cadastro simulado, pela conversa e pelo formulário, para a J3 e a J4.
 * FR-5, FR-6 e FR-8, seções 7.2, 8.5 e 12 do SDD.
 *
 * `installRegistrationApi` imita por `page.route` a máquina de estados da
 * seção 7.2: um campo por turno, opcionais que aceitam pular, senha, revisão
 * e aceite. `registerByChat` percorre a J3 inteira na tela e serve a
 * `registration.spec.ts` e a `motion.spec.ts`. Nada aqui fala com a API nem
 * com banco.
 */
import { expect, type Page, type Route } from "@playwright/test"

import { pt } from "../src/i18n/pt.ts"

const sessionId = "00000000-0000-4000-8000-0000000000f1"
const version = "2026-10-25.1"
const taken = "Este e-mail já tem uma conta. Entre para continuar."

/** Os campos entendidos, como em `fields` da seção 12. */
type Fields = {
  full_name: string | null
  email: string | null
  phone: string | null
  visitor_type: string | null
  visit_reason: string | null
}

/**
 * Simula a API do cadastro com o estado em memória.
 *
 * - O chat anda pelos passos `full_name`, `email`, `phone`, `visitor_type`,
 *   `visit_reason`, `password`, `review` e `acceptance`, os mesmos valores de
 *   `next_step` da API.
 * - Um e-mail com "usado" vira erro de campo no chat, sem trocar o e-mail
 *   guardado, e 409 no formulário (seção 12).
 * - A senha precisa de 12 a 72 caracteres (seção 8.5).
 * - Aceite ou formulário sem os Termos ou sem a maioridade responde 422, com
 *   `field_errors` (FR-8).
 * - `GET /v1/me` responde 401 até a conta existir. As rotas fora da lista
 *   também respondem 401.
 */
export async function installRegistrationApi(page: Page) {
  const fields: Fields = {
    full_name: null,
    email: null,
    phone: null,
    visitor_type: null,
    visit_reason: null,
  }
  let step = "full_name"
  let status = "collecting_required"
  let fieldErrors: Record<string, string> = {}
  let loggedIn = false
  let clock = 0
  const messages: Array<{
    role: "user" | "assistant"
    text: string
    created_at: string
  }> = [
    {
      role: "assistant",
      text: "Qual é o seu nome completo?",
      created_at: stamp(clock),
    },
  ]

  await page.route("**/backend/v1/**", async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    const method = request.method()

    if (method === "GET" && path.endsWith("/v1/legal/versions")) {
      await fulfill(route, 200, { terms: version, privacy_notice: version })
      return
    }
    if (method === "GET" && path.endsWith("/v1/me")) {
      await fulfill(
        route,
        loggedIn ? 200 : 401,
        loggedIn
          ? profile(fields)
          : error("unauthenticated", "Entre para continuar.")
      )
      return
    }
    if (method === "POST" && path.endsWith("/v1/registration/sessions")) {
      await fulfill(route, 201, snapshot())
      return
    }
    if (method === "GET" && path.includes("/v1/registration/sessions/")) {
      await fulfill(route, 200, snapshot())
      return
    }
    if (method === "POST" && path.endsWith("/messages")) {
      const body = request.postDataJSON() as { text?: string }
      applyMessage(body.text ?? "")
      await fulfill(route, 200, snapshot())
      return
    }
    if (method === "POST" && path.endsWith("/password")) {
      const body = request.postDataJSON() as { password?: string }
      const password = body.password ?? ""
      if (password.length < 12 || password.length > 72) {
        fieldErrors = { password: pt.registration.passwordInvalid }
      } else {
        fieldErrors = {}
        step = "review"
        status = "awaiting_review"
        push(
          "assistant",
          "Revise os dados no resumo. Se estiver certo, confirme."
        )
      }
      await fulfill(route, 200, snapshot())
      return
    }
    if (method === "POST" && path.endsWith("/review")) {
      const body = request.postDataJSON() as { accept?: boolean }
      if (body.accept) {
        step = "acceptance"
        status = "awaiting_acceptance"
        push(
          "assistant",
          "Para criar a conta, aceite os Termos e confirme a maioridade."
        )
      } else {
        step = "full_name"
        status = "collecting_required"
        push("assistant", "O que você quer corrigir no cadastro?")
      }
      await fulfill(route, 200, snapshot())
      return
    }
    if (method === "POST" && path.endsWith("/acceptance")) {
      const body = request.postDataJSON() as {
        accept_terms?: boolean
        age_18_plus?: boolean
      }
      if (!body.accept_terms || !body.age_18_plus) {
        await fulfill(
          route,
          422,
          error("validation_error", "Não foi possível concluir o cadastro.", {
            ...(body.accept_terms
              ? {}
              : { accept_terms: pt.registration.termsRequired }),
            ...(body.age_18_plus
              ? {}
              : { age_18_plus: pt.registration.ageRequired }),
          })
        )
        return
      }
      loggedIn = true
      await fulfill(route, 200, profile(fields))
      return
    }
    if (method === "POST" && path.endsWith("/v1/registration/form")) {
      const body = request.postDataJSON() as {
        full_name?: string
        email?: string
        accept_terms?: boolean
        age_18_plus?: boolean
      }
      if (body.email?.includes("usado")) {
        await fulfill(route, 409, error("conflict", taken, { email: taken }))
        return
      }
      if (!body.accept_terms || !body.age_18_plus) {
        await fulfill(
          route,
          422,
          error("validation_error", "Não foi possível concluir o cadastro.", {
            ...(body.accept_terms
              ? {}
              : { accept_terms: pt.registration.termsRequired }),
            ...(body.age_18_plus
              ? {}
              : { age_18_plus: pt.registration.ageRequired }),
          })
        )
        return
      }
      fields.full_name = body.full_name ?? fields.full_name
      fields.email = body.email ?? fields.email
      loggedIn = true
      await fulfill(route, 200, profile(fields))
      return
    }
    await fulfill(route, 401, error("unauthenticated", "Entre para continuar."))
  })

  /**
   * Aplica um turno do chat: guarda a mensagem, entende o campo do passo atual
   * e avança. O botão Pular manda `pt.registration.skipMessage`, que contém
   * "pular". Nos passos `visitor_type` e `visit_reason`, qualquer texto só
   * avança, sem gravar o campo.
   */
  function applyMessage(text: string) {
    push("user", text)
    fieldErrors = {}
    if (step === "full_name") {
      fields.full_name = text
      step = "email"
      push("assistant", "Qual é o seu e-mail?")
      return
    }
    if (step === "email") {
      if (text.includes("usado")) {
        fieldErrors = { email: taken }
        push("assistant", taken)
        return
      }
      fields.email = text
      step = "phone"
      status = "collecting_optional"
      push("assistant", "Qual é o seu telefone? Você pode pular este campo.")
      return
    }
    if (step === "phone") {
      if (!text.toLowerCase().includes("pular")) {
        fields.phone = text
      }
      step = "visitor_type"
      push("assistant", "Você está aqui como paciente, visita ou cuidador?")
      return
    }
    if (step === "visitor_type") {
      step = "visit_reason"
      push("assistant", "Qual é o motivo da visita?")
      return
    }
    step = "password"
    status = "awaiting_password"
    push("assistant", pt.registration.passwordNote)
  }

  /** Acrescenta uma mensagem à transcrição, um segundo depois da anterior. */
  function push(role: "user" | "assistant", text: string) {
    clock += 1
    messages.push({ role, text, created_at: stamp(clock) })
  }

  /**
   * A resposta da sessão, com os campos da seção 12. `prompt` é a última
   * mensagem da transcrição.
   */
  function snapshot() {
    return {
      id: sessionId,
      status,
      path: "chat",
      fields: { ...fields },
      field_errors: { ...fieldErrors },
      next_step: step,
      prompt: messages.at(-1)?.text ?? "",
      messages: messages.map((message) => ({ ...message })),
      expires_at: "2026-10-29T00:00:00.000Z",
    }
  }
}

/**
 * Faz a J3 na tela: nome, e-mail, três opcionais pulados, senha, revisão e
 * aceite, até a página da conta. Confere que o foco chega sozinho ao campo de
 * senha depois da M12 (seção 16.6). Precisa do `installRegistrationApi`.
 */
export async function registerByChat(page: Page) {
  await page.goto("/register")
  await page.getByLabel(pt.registration.messageLabel).fill("Ana Costa")
  await page.getByRole("button", { name: pt.registration.send }).click()
  await expect(page.getByText("Ana Costa").first()).toBeVisible()
  await page.getByLabel(pt.registration.messageLabel).fill("ana@example.com")
  await page.getByRole("button", { name: pt.registration.send }).click()
  await page.getByRole("button", { name: pt.registration.skip }).click()
  await page.getByRole("button", { name: pt.registration.skip }).click()
  await page.getByRole("button", { name: pt.registration.skip }).click()
  const password = page.getByRole("textbox", {
    name: pt.registration.fields.password,
    exact: true,
  })
  await expect(password).toBeFocused()
  await password.fill("senha-segura-1")
  await page.getByRole("button", { name: pt.registration.send }).click()
  await page.getByRole("button", { name: pt.registration.confirm }).click()
  await page.getByRole("checkbox", { name: pt.registration.terms }).check()
  await page.getByRole("checkbox", { name: pt.registration.age }).check()
  await page
    .getByRole("button", { name: pt.registration.createAccount })
    .click()
  await expect(
    page.getByRole("heading", { name: pt.pages.account })
  ).toBeVisible()
}

/**
 * O perfil de `GET /v1/me` montado dos campos, com um nome e um e-mail
 * padrão para o que faltar.
 */
function profile(fields: Fields) {
  return {
    id: "00000000-0000-4000-8000-0000000000aa",
    email: fields.email ?? "ana@example.com",
    full_name: fields.full_name ?? "Ana Costa",
    phone: fields.phone,
    visitor_type: fields.visitor_type,
    visit_reason: fields.visit_reason,
    role: "member",
    needs_legal_acceptance: false,
  }
}

/** O envelope de erro da seção 12, com `field_errors` opcional. */
function error(
  code: string,
  message: string,
  fieldErrors?: Record<string, string>
) {
  return {
    error: {
      code,
      message,
      request_id: "01E2E",
      field_errors: fieldErrors,
    },
  }
}

/** Um horário fixo de 2026-10-28, `index` segundos depois do meio-dia. */
function stamp(index: number) {
  return `2026-10-28T12:00:${String(index).padStart(2, "0")}.000Z`
}

/** Responde à rota com o status pedido e o corpo em JSON. */
function fulfill(route: Route, status: number, body: unknown) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  })
}
