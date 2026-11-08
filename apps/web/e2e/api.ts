/**
 * Conversa simulada e axe da suíte e2e. Seções 7.1, 15.3 e 15.8 do SDD.
 *
 * `installConversationApi` responde por `page.route` às rotas de `/v1` que a
 * J1 e a J2 usam, com o fluxo SSE da seção 7.1 escrito à mão.
 * `journeys.spec.ts` e `motion.spec.ts` usam essas respostas.
 * `expectNoSeriousViolations` e `visitingQuestion` servem também à suíte ao
 * vivo, por `live/fixtures.ts`. Nada aqui fala com a API nem com banco.
 */
import AxeBuilder from "@axe-core/playwright"
import { expect, type Page } from "@playwright/test"

import { pt } from "../src/i18n/pt.ts"

const conversationId = "00000000-0000-4000-8000-0000000000a1"
const assistantId = "00000000-0000-4000-8000-0000000000b1"
const chunkId = "00000000-0000-4000-8000-0000000000c1"

// O marcador `[1]` corresponde à citação de índice 1 de `visitingStream`.
const visitingAnswer = "O horário de visita é das 11:00 às 20:00 [1]."
// Começo da resposta fixa de orientação médica da seção 10.1.
const medicalAnswer =
  "Não posso ajudar com sintomas, diagnóstico ou medicamento. Se for uma emergência, ligue para o número local de emergência."

/**
 * Simula as rotas de `/backend/v1` de uma conversa de convidado.
 *
 * - `POST /v1/conversations` cria a conversa, sempre com o mesmo id.
 * - `POST .../messages` responde em `text/event-stream`. Uma pergunta com
 *   "remédio" recebe a recusa fixa, com desfecho `refused`. Qualquer outra
 *   recebe a resposta do horário de visita, com uma citação e `answered`.
 * - `GET /v1/conversations/{id}` devolve a conversa como o banco a guardaria,
 *   para a recarga da J1.
 * - Qualquer outra rota, inclusive `GET /v1/me`, responde 401: o visitante
 *   não tem sessão.
 */
export async function installConversationApi(page: Page) {
  let mode: "empty" | "visiting" | "medical" = "empty"
  await page.route("**/backend/v1/**", async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (request.method() === "POST" && url.pathname.endsWith("/v1/conversations")) {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: conversationId,
          created_at: "2026-10-27T12:00:00.000Z",
        }),
      })
      return
    }
    if (
      request.method() === "POST" &&
      url.pathname.endsWith(`/v1/conversations/${conversationId}/messages`)
    ) {
      const body = request.postDataJSON() as { text?: string }
      mode = body.text?.includes("remédio") ? "medical" : "visiting"
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: mode === "medical" ? medicalStream() : visitingStream(),
      })
      return
    }
    if (
      request.method() === "GET" &&
      url.pathname.endsWith(`/v1/conversations/${conversationId}`)
    ) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(stored(mode)),
      })
      return
    }
    await route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "unauthenticated",
          message: "Entre para continuar.",
          request_id: "01E2E",
        },
      }),
    })
  })
}

/**
 * Roda o axe na página inteira e falha com a lista das violações `serious` e
 * `critical`. As de impacto `minor` e `moderate` não reprovam. Seção 15.8.
 */
export async function expectNoSeriousViolations(page: Page) {
  const results = await new AxeBuilder({ page }).analyze()
  const serious = results.violations.filter((violation) => {
    return violation.impact === "serious" || violation.impact === "critical"
  })
  expect(serious.map((violation) => `${violation.id}: ${violation.help}`)).toEqual(
    [],
  )
}

/**
 * A primeira sugestão da tela inicial, com `label` e `question`: a pergunta do
 * horário de visita da J1.
 */
export function visitingQuestion() {
  return pt.ask.suggestions[0]
}

/** Fluxo da J1 na ordem da seção 7.1: `meta`, `token`, `citation` e `done`. */
function visitingStream() {
  return [
    event("meta", { message_id: assistantId, request_id: "req-visit" }),
    event("token", { text: visitingAnswer }),
    event("citation", {
      index: 1,
      document_title: "Visitas",
      heading: "Horário",
      chunk_id: chunkId,
    }),
    event("done", { outcome: "answered" }),
  ].join("")
}

/** Fluxo da J2: a resposta fixa num `token` só e `done` com `refused`. */
function medicalStream() {
  return [
    event("meta", { message_id: assistantId, request_id: "req-health" }),
    event("token", { text: medicalAnswer }),
    event("done", { outcome: "refused" }),
  ].join("")
}

/**
 * A conversa que `GET /v1/conversations/{id}` devolve em cada modo. Na
 * recusa, a mensagem do visitante traz o marcador da seção 7.1, não a
 * pergunta (FR-17).
 */
function stored(mode: "empty" | "visiting" | "medical") {
  if (mode === "empty") {
    return {
      id: conversationId,
      created_at: "2026-10-27T12:00:00.000Z",
      messages: [],
    }
  }
  if (mode === "medical") {
    return {
      id: conversationId,
      created_at: "2026-10-27T12:00:00.000Z",
      messages: [
        {
          id: "00000000-0000-4000-8000-0000000000d1",
          role: "user",
          content: "[health-related message not stored]",
          client_message_id: "00000000-0000-4000-8000-0000000000e1",
          citations: [],
          outcome: null,
          created_at: "2026-10-27T12:00:01.000Z",
        },
        {
          id: assistantId,
          role: "assistant",
          content: medicalAnswer,
          client_message_id: null,
          citations: [],
          outcome: "refused",
          created_at: "2026-10-27T12:00:02.000Z",
        },
      ],
    }
  }
  return {
    id: conversationId,
    created_at: "2026-10-27T12:00:00.000Z",
    messages: [
      {
        id: "00000000-0000-4000-8000-0000000000d1",
        role: "user",
        content: visitingQuestion().question,
        client_message_id: "00000000-0000-4000-8000-0000000000e1",
        citations: [],
        outcome: null,
        created_at: "2026-10-27T12:00:01.000Z",
      },
      {
        id: assistantId,
        role: "assistant",
        content: visitingAnswer,
        client_message_id: null,
        citations: [
          {
            index: 1,
            document_title: "Visitas",
            heading: "Horário",
            chunk_id: chunkId,
          },
        ],
        outcome: "answered",
        created_at: "2026-10-27T12:00:02.000Z",
      },
    ],
  }
}

/** Um evento SSE: as linhas `event:` e `data:` e a linha em branco final. */
function event(name: string, payload: unknown) {
  return `event: ${name}\ndata: ${JSON.stringify(payload)}\n\n`
}
