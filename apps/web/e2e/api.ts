import AxeBuilder from "@axe-core/playwright"
import { expect, type Page } from "@playwright/test"

import { pt } from "../src/i18n/pt.ts"

const conversationId = "00000000-0000-4000-8000-0000000000a1"
const assistantId = "00000000-0000-4000-8000-0000000000b1"
const chunkId = "00000000-0000-4000-8000-0000000000c1"

const visitingAnswer = "O horário de visita é das 11:00 às 20:00 [1]."
const medicalAnswer =
  "Não posso ajudar com sintomas, diagnóstico ou medicamento. Se for uma emergência, ligue para o número local de emergência."

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

export async function expectNoSeriousViolations(page: Page) {
  const results = await new AxeBuilder({ page }).analyze()
  const serious = results.violations.filter((violation) => {
    return violation.impact === "serious" || violation.impact === "critical"
  })
  expect(serious.map((violation) => `${violation.id}: ${violation.help}`)).toEqual(
    [],
  )
}

export function visitingQuestion() {
  return pt.ask.suggestions[0]
}

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

function medicalStream() {
  return [
    event("meta", { message_id: assistantId, request_id: "req-health" }),
    event("token", { text: medicalAnswer }),
    event("done", { outcome: "refused" }),
  ].join("")
}

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

function event(name: string, payload: unknown) {
  return `event: ${name}\ndata: ${JSON.stringify(payload)}\n\n`
}
