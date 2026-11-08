/**
 * Conta simulada de um membro, para a J5. FR-9 e seções 11.5, 12 e 15.3 do
 * SDD.
 *
 * `installAccountApi` responde por `page.route` às rotas do perfil, dos
 * consentimentos, da exportação, da exclusão e das conversas, com o estado do
 * membro em memória. `account.spec.ts` lê esse estado para conferir o que a
 * tela mandou. Nada aqui fala com a API nem com banco.
 */
import type { Page, Route } from "@playwright/test"

const version = "2026-10-25.1"
const stamp = "2026-11-03T12:00:00.000Z"

/** O perfil de `GET /v1/me` (seção 12). */
type Member = {
  id: string
  email: string
  full_name: string
  phone: string | null
  visitor_type: string | null
  visit_reason: string | null
  role: "member"
  needs_legal_acceptance: boolean
}

/**
 * O que o teste lê do falso: se a conta foi excluída, se os dados foram
 * exportados e o perfil como está agora.
 */
export type AccountApi = {
  deleted: () => boolean
  exported: () => boolean
  member: () => Member
}

/**
 * Simula a API da conta com um membro que já tem sessão.
 *
 * - `PATCH /v1/me` aplica o corpo no perfil.
 * - Revogar a personalização apaga `visitor_type` e `visit_reason`, como na
 *   seção 12.
 * - A exportação responde com `Content-Disposition: attachment` e o arquivo
 *   `atrium-meus-dados.json`.
 * - `DELETE /v1/me` responde 204 e encerra a sessão: depois dele,
 *   `GET /v1/me` responde 401.
 * - Rotas fora da lista respondem 404.
 */
export async function installAccountApi(page: Page): Promise<AccountApi> {
  let signedIn = true
  let deleted = false
  let exported = false
  let personalization = false
  const member: Member = {
    id: "00000000-0000-4000-8000-0000000000d1",
    email: "ana@example.com",
    full_name: "Ana Souza",
    phone: null,
    visitor_type: null,
    visit_reason: null,
    role: "member",
    needs_legal_acceptance: false,
  }

  await page.route("**/backend/v1/**", async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    const method = request.method()

    if (method === "GET" && path.endsWith("/v1/me")) {
      if (!signedIn) {
        await fulfill(route, 401, error("unauthenticated", "Entre para continuar."))
        return
      }
      await fulfill(route, 200, member)
      return
    }
    if (method === "PATCH" && path.endsWith("/v1/me")) {
      Object.assign(member, request.postDataJSON() as Partial<Member>)
      await fulfill(route, 200, member)
      return
    }
    if (method === "GET" && path.endsWith("/v1/me/consents")) {
      await fulfill(route, 200, consents(personalization))
      return
    }
    if (method === "PUT" && path.endsWith("/v1/me/consents/profile_personalization")) {
      personalization = (request.postDataJSON() as { granted: boolean }).granted
      if (!personalization) {
        member.visitor_type = null
        member.visit_reason = null
      }
      await fulfill(route, 200, consents(personalization))
      return
    }
    if (method === "GET" && path.endsWith("/v1/me/export")) {
      exported = true
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: {
          "content-disposition": 'attachment; filename="atrium-meus-dados.json"',
        },
        body: JSON.stringify({
          exported_at: stamp,
          profile: { email: member.email, full_name: member.full_name },
          consents: [],
          conversations: [],
        }),
      })
      return
    }
    if (method === "DELETE" && path.endsWith("/v1/me")) {
      deleted = true
      signedIn = false
      await route.fulfill({ status: 204 })
      return
    }
    if (method === "GET" && path.endsWith("/v1/conversations")) {
      await fulfill(route, 200, {
        conversations: [
          {
            id: "00000000-0000-4000-8000-0000000000a1",
            created_at: stamp,
            first_question: "Qual é o horário de visita?",
          },
        ],
      })
      return
    }
    await fulfill(route, 404, error("not_found", "Não encontrei isso."))
  })

  return {
    deleted: () => deleted,
    exported: () => exported,
    member: () => member,
  }
}

/**
 * O corpo de `GET /v1/me/consents`: Termos e maioridade concedidos, a
 * personalização conforme o estado e a melhoria desligada. `history` vem
 * vazio.
 */
function consents(personalization: boolean) {
  const state = (purpose: string, on: boolean) => ({
    purpose,
    granted: on,
    document_version: on ? version : null,
    granted_at: on ? stamp : null,
  })
  return {
    current: [
      state("terms_and_privacy_notice", true),
      state("age_18_plus", true),
      state("profile_personalization", personalization),
      state("quality_improvement", false),
    ],
    history: [],
  }
}

/** O envelope de erro da seção 12. */
function error(code: string, message: string) {
  return { error: { code, message, request_id: "01E2E" } }
}

/** Responde à rota com o status pedido e o corpo em JSON. */
function fulfill(route: Route, status: number, body: unknown) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  })
}
