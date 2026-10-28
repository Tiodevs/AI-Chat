import { announcementFor, syncPrivacy } from "./model.ts"
import type { AskSnapshot, AssistantTurn, Turn } from "./types.ts"

const BUDGET_KEY = "atrium.budget-exceeded"

type Entry = {
  snapshot: AskSnapshot
}

const listeners = new Set<() => void>()
const entries = new Map<string, Entry>()
const controllers = new Map<string, AbortController>()
let pendingQuestion: { id: string; text: string } | null = null
let home = blank()
let empty = blank()

export function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function selectAsk(conversationId: string | undefined): AskSnapshot {
  if (!conversationId) {
    return home
  }
  return entries.get(conversationId)?.snapshot ?? empty
}

export function stageQuestion(conversationId: string, text: string) {
  pendingQuestion = { id: conversationId, text }
}

export function takeQuestion(conversationId: string): string | null {
  if (pendingQuestion?.id !== conversationId) {
    return null
  }
  const text = pendingQuestion.text
  pendingQuestion = null
  return text
}

export function patchAsk(
  conversationId: string | undefined,
  partial: Partial<AskSnapshot>
) {
  write(conversationId, partial)
  emit()
}

export function appendTurns(conversationId: string, turns: Turn[]) {
  const current = ensure(conversationId).snapshot
  write(conversationId, {
    messages: syncPrivacy([...current.messages, ...turns]),
    loading: false,
    error: null,
    rateLimit: null,
    streaming: true,
  })
  emit()
}

export function updateAssistant(
  conversationId: string,
  assistantKey: string,
  turn: AssistantTurn
) {
  const current = ensure(conversationId).snapshot
  const messages = syncPrivacy(
    current.messages.map((message) => {
      return message.key === assistantKey ? turn : message
    })
  )
  const announced = announcementFor(turn)
  write(conversationId, {
    messages,
    live: announced || current.live,
    streaming: turn.phase === "waiting" || turn.phase === "streaming",
  })
  emit()
}

export function replaceMessages(
  conversationId: string,
  messages: Turn[],
  announce: boolean
) {
  const synced = syncPrivacy(messages)
  const latest = [...synced]
    .reverse()
    .find((message) => message.role === "assistant")
  write(conversationId, {
    messages: synced,
    loading: false,
    streaming: false,
    live:
      announce && latest && latest.role === "assistant"
        ? announcementFor(latest)
        : ensure(conversationId).snapshot.live,
  })
  emit()
}

export function markBudgetExceeded() {
  try {
    sessionStorage.setItem(BUDGET_KEY, "1")
  } catch {
    // O estado em memória continua valendo quando o armazenamento está bloqueado.
  }
  const withBudget = (snapshot: AskSnapshot): AskSnapshot => ({
    ...snapshot,
    budgetExceeded: true,
  })
  empty = withBudget(empty)
  home = withBudget(home)
  for (const entry of entries.values()) {
    entry.snapshot = withBudget(entry.snapshot)
  }
  emit()
}

export function openStream(conversationId: string) {
  controllers.get(conversationId)?.abort()
  const controller = new AbortController()
  controllers.set(conversationId, controller)
  return controller
}

export function releaseStream(
  conversationId: string,
  controller: AbortController
) {
  if (controllers.get(conversationId) !== controller) {
    return
  }
  controllers.delete(conversationId)
  const current = entries.get(conversationId)
  if (!current?.snapshot.streaming) {
    return
  }
  write(conversationId, { streaming: false })
  emit()
}

export function stopStream(conversationId: string) {
  controllers.get(conversationId)?.abort()
  controllers.delete(conversationId)
  const current = entries.get(conversationId)
  if (!current) {
    return
  }
  const messages = current.snapshot.messages.map((message) => message)
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    if (
      message?.role === "assistant" &&
      (message.phase === "waiting" || message.phase === "streaming")
    ) {
      messages[index] = {
        ...message,
        phase: "cancelled",
        text: "",
        outgoing: null,
      }
      break
    }
  }
  write(conversationId, {
    messages,
    streaming: false,
    live: announcementFor({
      key: "cancelled",
      role: "assistant",
      id: null,
      requestId: null,
      text: "",
      outgoing: null,
      citations: [],
      outcome: "cancelled",
      phase: "cancelled",
      replaced: false,
      errorMessage: null,
      feedback: null,
      retryText: null,
    }),
  })
  emit()
}

export function dropAssistant(conversationId: string, assistantKey: string) {
  const current = ensure(conversationId).snapshot
  write(conversationId, {
    messages: current.messages.filter(
      (message) => message.key !== assistantKey
    ),
    streaming: false,
  })
  emit()
}

export function resetAskState() {
  for (const controller of controllers.values()) {
    controller.abort()
  }
  controllers.clear()
  entries.clear()
  pendingQuestion = null
  try {
    sessionStorage.removeItem(BUDGET_KEY)
  } catch {
    // O navegador pode bloquear o armazenamento. O estado em memória segue limpo.
  }
  home = blank()
  empty = blank()
  emit()
}

function ensure(conversationId: string) {
  const existing = entries.get(conversationId)
  if (existing) {
    return existing
  }
  const created = {
    snapshot: { ...blank(), budgetExceeded: empty.budgetExceeded },
  }
  entries.set(conversationId, created)
  return created
}

function write(
  conversationId: string | undefined,
  partial: Partial<AskSnapshot>
) {
  if (!conversationId) {
    home = { ...home, ...partial }
    return
  }
  const entry = ensure(conversationId)
  entry.snapshot = { ...entry.snapshot, ...partial }
}

function emit() {
  for (const listener of listeners) {
    listener()
  }
}

export type { AskSnapshot }

function blank(): AskSnapshot {
  return {
    messages: [],
    live: "",
    loading: false,
    pending: false,
    streaming: false,
    error: null,
    requestId: null,
    rateLimit: null,
    budgetExceeded: readBudget(),
  }
}

function readBudget() {
  try {
    return sessionStorage.getItem(BUDGET_KEY) === "1"
  } catch {
    return false
  }
}
