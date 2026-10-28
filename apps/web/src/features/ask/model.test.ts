import { describe, expect, it } from "vitest"

import { pt } from "@/i18n/pt.ts"

import {
  announcementFor,
  applyStreamEvent,
  questionLimit,
  syncPrivacy,
  turnsFromStored,
} from "./model.ts"
import { HEALTH_MARKER, type AssistantTurn } from "./types.ts"

const waiting: AssistantTurn = {
  key: "assistant",
  role: "assistant",
  id: null,
  requestId: null,
  text: "",
  outgoing: null,
  citations: [],
  outcome: null,
  phase: "waiting",
  replaced: false,
  errorMessage: null,
  feedback: null,
  retryText: "Qual é o horário de visita?",
}

describe("conversa", () => {
  it("troca o rascunho quando chega replace", () => {
    const streamed = applyStreamEvent(waiting, {
      event: "token",
      data: JSON.stringify({ text: "rascunho ruim" }),
    })
    const replaced = applyStreamEvent(streamed, {
      event: "replace",
      data: JSON.stringify({
        text: "texto seguro",
        reason: "grounding_failed",
      }),
    })
    expect(replaced.text).toBe("texto seguro")
    expect(replaced.outgoing).toBe("rascunho ruim")
    expect(replaced.replaced).toBe(true)
    expect(announcementFor(replaced)).toBe("")
    const done = applyStreamEvent(replaced, {
      event: "done",
      data: JSON.stringify({ outcome: "grounding_failed" }),
    })
    expect(announcementFor(done)).toBe(`${pt.ask.replacedNote} texto seguro`)
  })

  it("não anuncia token antes do done", () => {
    const streamed = applyStreamEvent(waiting, {
      event: "token",
      data: JSON.stringify({ text: "pedaço" }),
    })
    expect(streamed.phase).toBe("streaming")
    expect(announcementFor(streamed)).toBe("")
  })

  it("esconde a pergunta médica gravada com o marcador", () => {
    const turns = syncPrivacy(
      turnsFromStored([
        {
          id: "user",
          role: "user",
          content: HEALTH_MARKER,
          clientMessageId: "user",
          citations: [],
          outcome: null,
        },
        {
          id: "assistant",
          role: "assistant",
          content: "Não posso ajudar.",
          clientMessageId: null,
          citations: [],
          outcome: "refused",
        },
      ])
    )
    const user = turns[0]
    expect(user?.role).toBe("user")
    if (user?.role === "user") {
      expect(user.privacy).toBe(true)
      expect(user.text).toBe("")
    }
  })

  it("mostra o limite em minutos", () => {
    expect(questionLimit(30)).toBe(pt.ask.limitedOne)
    expect(questionLimit(90)).toBe(pt.ask.limitedMany.replace("{minutes}", "2"))
  })
})
