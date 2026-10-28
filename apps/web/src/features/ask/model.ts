import { pt } from "@/i18n/pt.ts"

import {
  HEALTH_MARKER,
  type AssistantTurn,
  type CitationView,
  type StoredMessage,
  type Turn,
  type UserTurn,
} from "./types.ts"

export function questionLimit(retryAfterSeconds: number): string {
  const minutes = Math.max(1, Math.ceil(retryAfterSeconds / 60))
  if (minutes === 1) {
    return pt.ask.limitedOne
  }
  return pt.ask.limitedMany.replace("{minutes}", String(minutes))
}

export function turnsFromStored(messages: StoredMessage[]): Turn[] {
  const turns: Turn[] = []
  let lastUserText: string | null = null
  for (const message of messages) {
    if (message.role === "user") {
      const privacy = message.content === HEALTH_MARKER
      lastUserText = privacy ? null : message.content
      const user: UserTurn = {
        key: message.id,
        role: "user",
        text: privacy ? "" : message.content,
        clientMessageId: message.clientMessageId ?? message.id,
        privacy,
      }
      turns.push(user)
      continue
    }
    const cancelled = message.outcome === "cancelled"
    const assistant: AssistantTurn = {
      key: message.id,
      role: "assistant",
      id: message.id,
      requestId: null,
      text: message.content,
      outgoing: null,
      citations: message.citations,
      outcome: message.outcome,
      phase: cancelled ? "cancelled" : message.outcome ? "done" : "waiting",
      replaced: false,
      errorMessage: null,
      feedback: null,
      retryText: cancelled ? lastUserText : null,
    }
    turns.push(assistant)
  }
  return turns
}

export function applyStreamEvent(
  turn: AssistantTurn,
  event: { event: string; data: string }
): AssistantTurn {
  const body = readPayload(event.data)
  if (event.event === "meta") {
    return {
      ...turn,
      id: textField(body, "message_id") ?? turn.id,
      requestId: textField(body, "request_id") ?? turn.requestId,
    }
  }
  if (event.event === "token") {
    return {
      ...turn,
      text: turn.text + (textField(body, "text") ?? ""),
      phase: "streaming",
    }
  }
  if (event.event === "replace") {
    return {
      ...turn,
      outgoing: turn.text,
      text: textField(body, "text") ?? "",
      citations: [],
      replaced: true,
      phase: "streaming",
    }
  }
  if (event.event === "citation") {
    const citation = citationFrom(body)
    if (!citation) {
      return turn
    }
    return { ...turn, citations: [...turn.citations, citation] }
  }
  if (event.event === "done") {
    const outcome = textField(body, "outcome")
    return {
      ...turn,
      outcome,
      phase: outcome === "cancelled" ? "cancelled" : "done",
    }
  }
  if (event.event === "error") {
    return {
      ...turn,
      phase: "error",
      text: "",
      errorMessage: textField(body, "message") ?? pt.ask.couldNotFinish,
    }
  }
  return turn
}

export function syncPrivacy(messages: Turn[]): Turn[] {
  return messages.map((message, index) => {
    if (message.role !== "user" || message.privacy) {
      return message
    }
    const following = messages[index + 1]
    if (following?.role === "assistant" && following.outcome === "refused") {
      return { ...message, privacy: true }
    }
    return message
  })
}

export function announcementFor(turn: AssistantTurn): string {
  if (turn.phase === "waiting" || turn.phase === "streaming") {
    return ""
  }
  if (turn.phase === "cancelled") {
    return pt.ask.interrupted
  }
  if (turn.phase === "error") {
    return turn.errorMessage ?? pt.ask.couldNotFinish
  }
  if (turn.outcome === "refused") {
    return `${turn.text} ${pt.ask.privacyNote}`
  }
  if (turn.replaced) {
    return `${pt.ask.replacedNote} ${turn.text}`
  }
  return turn.text
}

export function assistantAfter(
  messages: StoredMessage[],
  clientMessageId: string
): StoredMessage | null {
  const userIndex = messages.findIndex((message) => {
    return (
      message.role === "user" && message.clientMessageId === clientMessageId
    )
  })
  if (userIndex < 0) {
    return null
  }
  return (
    messages.slice(userIndex + 1).find((message) => {
      return message.role === "assistant" && message.outcome !== null
    }) ?? null
  )
}

function citationFrom(body: Record<string, unknown>): CitationView | null {
  const index = body.index
  const title = textField(body, "document_title")
  const chunkId = textField(body, "chunk_id")
  if (typeof index !== "number" || !title || !chunkId) {
    return null
  }
  return {
    index,
    documentTitle: title,
    heading: body.heading == null ? null : String(body.heading),
    chunkId,
  }
}

function readPayload(data: string): Record<string, unknown> {
  const parsed: unknown = JSON.parse(data)
  if (!parsed || typeof parsed !== "object") {
    return {}
  }
  return parsed as Record<string, unknown>
}

function textField(body: Record<string, unknown>, key: string): string | null {
  const value = body[key]
  return typeof value === "string" ? value : null
}
