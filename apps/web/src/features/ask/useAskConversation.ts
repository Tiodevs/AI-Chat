import { useEffect, useSyncExternalStore } from "react"
import { useNavigate } from "react-router"

import {
  messageFrom,
  requestIdFrom,
  retryAfterFrom,
} from "@/features/auth/api-error.ts"
import { pt } from "@/i18n/pt.ts"
import { api } from "@/lib/api/client.ts"
import type { components } from "@/lib/api/schema.ts"
import { postEventStream, readEventStream } from "@/lib/sse.ts"

import {
  applyStreamEvent,
  assistantAfter,
  questionLimit,
  turnsFromStored,
} from "./model.ts"
import {
  appendTurns,
  dropAssistant,
  markBudgetExceeded,
  openStream,
  patchAsk,
  releaseStream,
  replaceMessages,
  selectAsk,
  stageQuestion,
  stopStream,
  subscribe,
  takeQuestion,
  updateAssistant,
} from "./store.ts"
import type { AssistantTurn, StoredMessage } from "./types.ts"

const reserveEveryMs = 1000

type ApiMessage = components["schemas"]["MessageResponse"]

export function useAskConversation(conversationId: string | undefined) {
  const navigate = useNavigate()
  const snapshot = useSyncExternalStore(
    subscribe,
    () => selectAsk(conversationId),
    () => selectAsk(conversationId)
  )

  useEffect(() => {
    if (!conversationId) {
      return
    }
    const pending = takeQuestion(conversationId)
    if (pending) {
      void submit(conversationId, pending)
      return
    }
    const current = selectAsk(conversationId)
    if (current.loading || current.streaming || current.messages.length > 0) {
      return
    }
    void load(conversationId)
  }, [conversationId])

  async function start(text: string) {
    const trimmed = text.trim()
    if (
      !trimmed ||
      selectAsk(undefined).pending ||
      selectAsk(undefined).budgetExceeded
    ) {
      return
    }
    patchAsk(undefined, { pending: true, error: null, requestId: null })
    try {
      const created = await api.POST("/v1/conversations")
      if (!created.response.ok || !created.data) {
        patchAsk(undefined, {
          pending: false,
          error: messageFrom(created.error, pt.couldNotContinue),
          requestId: requestIdFrom(created.error),
        })
        return
      }
      stageQuestion(created.data.id, trimmed)
      patchAsk(undefined, { pending: false, error: null })
      await navigate(`/ask/${created.data.id}`)
    } catch {
      patchAsk(undefined, { pending: false, error: pt.couldNotContinue })
    }
  }

  function ask(text: string) {
    if (conversationId) {
      void submit(conversationId, text)
      return
    }
    void start(text)
  }

  return {
    messages: snapshot.messages,
    live: snapshot.live,
    loading: snapshot.loading,
    pending: snapshot.pending,
    streaming: snapshot.streaming,
    error: snapshot.error,
    requestId: snapshot.requestId,
    rateLimit: snapshot.rateLimit,
    budgetExceeded: snapshot.budgetExceeded,
    ask,
    stop() {
      if (conversationId) {
        stopStream(conversationId)
      }
    },
    feedback(messageId: string, rating: 1 | -1) {
      if (conversationId) {
        void sendFeedback(conversationId, messageId, rating)
      }
    },
  }
}

async function load(conversationId: string, force = false) {
  if (!force) {
    patchAsk(conversationId, { loading: true, error: null })
  }
  try {
    const result = await api.GET("/v1/conversations/{conversation_id}", {
      params: { path: { conversation_id: conversationId } },
    })
    if (!force && selectAsk(conversationId).streaming) {
      return
    }
    if (!result.response.ok || !result.data) {
      patchAsk(conversationId, {
        loading: false,
        error: messageFrom(result.error, pt.couldNotContinue),
        requestId: requestIdFrom(result.error),
      })
      return
    }
    replaceMessages(
      conversationId,
      turnsFromStored(result.data.messages.map(toStored)),
      false
    )
  } catch {
    if (!selectAsk(conversationId).streaming) {
      patchAsk(conversationId, { loading: false, error: pt.couldNotContinue })
    }
  }
}

async function submit(conversationId: string, text: string) {
  const trimmed = text.trim()
  const current = selectAsk(conversationId)
  if (!trimmed || current.streaming || current.budgetExceeded) {
    return
  }
  const clientMessageId = newId()
  const assistant = waitingAssistant(newId(), trimmed)
  appendTurns(conversationId, [
    {
      key: clientMessageId,
      role: "user",
      text: trimmed,
      clientMessageId,
      privacy: false,
    },
    assistant,
  ])
  const controller = openStream(conversationId)
  let draft = assistant
  let sawStream = false
  let finished = false
  let settledByPoll = false
  const timer = window.setInterval(() => {
    void reserve()
  }, reserveEveryMs)

  async function reserve() {
    if (sawStream || settledByPoll || controller.signal.aborted) {
      return
    }
    try {
      const result = await api.GET("/v1/conversations/{conversation_id}", {
        params: { path: { conversation_id: conversationId } },
      })
      if (
        sawStream ||
        settledByPoll ||
        controller.signal.aborted ||
        !result.data
      ) {
        return
      }
      const stored = result.data.messages.map(toStored)
      const settled = assistantAfter(stored, clientMessageId)
      if (!settled?.outcome) {
        return
      }
      settledByPoll = true
      window.clearInterval(timer)
      replaceMessages(conversationId, turnsFromStored(stored), true)
      if (settled.outcome === "degraded") {
        markBudgetExceeded()
      }
      controller.abort()
    } catch {
      // A reserva tenta de novo no próximo segundo.
    }
  }

  function commit(next: AssistantTurn) {
    draft = next
    updateAssistant(conversationId, assistant.key, next)
  }

  try {
    const response = await postEventStream(
      messageUrl(conversationId),
      { text: trimmed, client_message_id: clientMessageId },
      controller.signal
    )
    if (!response.ok) {
      await failHttp(conversationId, assistant.key, response)
      return
    }
    if (!response.body) {
      commit({
        ...draft,
        phase: "error",
        errorMessage: pt.ask.couldNotFinish,
      })
      return
    }
    for await (const event of readEventStream(response.body)) {
      if (controller.signal.aborted || settledByPoll) {
        return
      }
      sawStream = true
      try {
        commit(applyStreamEvent(draft, event))
      } catch {
        commit({
          ...draft,
          phase: "error",
          errorMessage: pt.ask.couldNotFinish,
        })
        return
      }
      if (event.event === "done" && draft.outcome === "degraded") {
        markBudgetExceeded()
      }
      if (event.event === "done" || event.event === "error") {
        finished = true
        return
      }
    }
    if (!finished && !settledByPoll && !controller.signal.aborted) {
      commit({
        ...draft,
        phase: "error",
        errorMessage: pt.ask.couldNotFinish,
      })
    }
  } catch {
    if (controller.signal.aborted || settledByPoll) {
      return
    }
    commit({
      ...draft,
      phase: "error",
      errorMessage: pt.couldNotContinue,
    })
  } finally {
    window.clearInterval(timer)
    releaseStream(conversationId, controller)
  }
}

async function failHttp(
  conversationId: string,
  assistantKey: string,
  response: Response
) {
  const body: unknown = await response.json().catch(() => null)
  if (response.status === 409) {
    await load(conversationId, true)
    return
  }
  if (response.status === 429) {
    dropAssistant(conversationId, assistantKey)
    patchAsk(conversationId, {
      rateLimit: questionLimit(retryAfterFrom(body) ?? 60),
      streaming: false,
    })
    return
  }
  if (response.status === 503) {
    markBudgetExceeded()
    const current = selectAsk(conversationId).messages.find((message) => {
      return message.key === assistantKey && message.role === "assistant"
    })
    if (current?.role === "assistant") {
      updateAssistant(conversationId, assistantKey, {
        ...current,
        phase: "done",
        outcome: "degraded",
        text: messageFrom(body, pt.ask.unavailable),
      })
    }
    return
  }
  const current = selectAsk(conversationId).messages.find((message) => {
    return message.key === assistantKey && message.role === "assistant"
  })
  if (current?.role === "assistant") {
    updateAssistant(conversationId, assistantKey, {
      ...current,
      phase: "error",
      errorMessage: messageFrom(body, pt.couldNotContinue),
      requestId: requestIdFrom(body),
    })
  }
}

async function sendFeedback(
  conversationId: string,
  messageId: string,
  rating: 1 | -1
) {
  const current = selectAsk(conversationId).messages.find((message) => {
    return message.role === "assistant" && message.id === messageId
  })
  if (!current || current.role !== "assistant" || current.feedback) {
    return
  }
  updateAssistant(conversationId, current.key, { ...current, feedback: rating })
  try {
    const result = await api.POST("/v1/messages/{message_id}/feedback", {
      params: { path: { message_id: messageId } },
      body: { rating },
    })
    if (result.response.ok) {
      return
    }
    const latest = selectAsk(conversationId).messages.find((message) => {
      return message.key === current.key && message.role === "assistant"
    })
    if (!latest || latest.role !== "assistant") {
      return
    }
    updateAssistant(conversationId, current.key, {
      ...latest,
      feedback: result.response.status === 409 ? "locked" : null,
    })
  } catch {
    const latest = selectAsk(conversationId).messages.find((message) => {
      return message.key === current.key && message.role === "assistant"
    })
    if (latest?.role === "assistant") {
      updateAssistant(conversationId, current.key, {
        ...latest,
        feedback: null,
      })
    }
  }
}

function waitingAssistant(key: string, retryText: string): AssistantTurn {
  return {
    key,
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
    retryText,
  }
}

function toStored(message: ApiMessage): StoredMessage {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    clientMessageId: message.client_message_id,
    outcome: message.outcome,
    citations: message.citations.map((citation) => ({
      index: citation.index,
      documentTitle: citation.document_title,
      heading: citation.heading,
      chunkId: citation.chunk_id,
    })),
  }
}

function messageUrl(conversationId: string) {
  const origin =
    window.location.origin === "null"
      ? "http://127.0.0.1"
      : window.location.origin
  return `${origin}/backend/v1/conversations/${conversationId}/messages`
}

function newId() {
  return globalThis.crypto.randomUUID()
}
