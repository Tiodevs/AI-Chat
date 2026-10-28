export const HEALTH_MARKER = "[health-related message not stored]"

export type CitationView = {
  index: number
  documentTitle: string
  heading: string | null
  chunkId: string
}

export type FeedbackState = 1 | -1 | "locked" | null

export type AssistantPhase =
  "waiting" | "streaming" | "done" | "cancelled" | "error"

export type UserTurn = {
  key: string
  role: "user"
  text: string
  clientMessageId: string
  privacy: boolean
}

export type AssistantTurn = {
  key: string
  role: "assistant"
  id: string | null
  requestId: string | null
  text: string
  outgoing: string | null
  citations: CitationView[]
  outcome: string | null
  phase: AssistantPhase
  replaced: boolean
  errorMessage: string | null
  feedback: FeedbackState
  retryText: string | null
}

export type Turn = UserTurn | AssistantTurn

export type AskSnapshot = {
  messages: Turn[]
  live: string
  loading: boolean
  pending: boolean
  streaming: boolean
  error: string | null
  requestId: string | null
  rateLimit: string | null
  budgetExceeded: boolean
}

export type StoredMessage = {
  id: string
  role: "user" | "assistant"
  content: string
  clientMessageId: string | null
  citations: CitationView[]
  outcome: string | null
}
