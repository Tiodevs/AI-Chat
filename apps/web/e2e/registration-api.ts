import { expect, type Page, type Route } from "@playwright/test"

import { pt } from "../src/i18n/pt.ts"

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
          "Revise os dados ao lado. Se estiver certo, confirme."
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

  function push(role: "user" | "assistant", text: string) {
    clock += 1
    messages.push({ role, text, created_at: stamp(clock) })
  }

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

function stamp(index: number) {
  return `2026-10-28T12:00:${String(index).padStart(2, "0")}.000Z`
}

function fulfill(route: Route, status: number, body: unknown) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  })
}
