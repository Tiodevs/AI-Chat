/**
 * Controlador do atendimento humano na conversa: disponibilidade, pedido,
 * mensagens, encerramento e o fluxo em tempo real. Seções 29.4 a 29.6 e
 * 29.11 do SDD.
 *
 * Usado por `app/routes/ask.tsx`, ao lado de `useAskConversation`. Usa o
 * cliente tipado (`lib/api/client.ts`) para os `POST` e `openEventStream`,
 * de `lib/sse.ts`, para o fluxo `GET /v1/conversations/{id}/handoff/events`,
 * com retomada pelo `Last-Event-ID`. O estado fica em `handoff-store.ts`, e
 * o bloco da thread entra em `store.ts` por `appendHandoffTurn`.
 *
 * Nada daqui fala com a IA: o texto do atendimento não vai ao modelo
 * (FR-21).
 */
import { useEffect, useSyncExternalStore } from "react"

import { messageFrom } from "@/features/auth/api-error.ts"
import { pt } from "@/i18n/pt.ts"
import { api } from "@/lib/api/client.ts"
import { openEventStream, type ServerEvent } from "@/lib/sse.ts"

import {
  activeHandoff,
  lastSeq,
  patchHandoff,
  selectHandoff,
  subscribeHandoff,
  upsertHandoff,
  upsertHandoffMessage,
  type Availability,
  type HandoffMessageView,
  type HandoffStatus,
} from "./handoff-store.ts"
import { appendHandoffTurn } from "./store.ts"

/** A disponibilidade é lida de novo a cada 30 segundos (seção 29.4). */
const availabilityEveryMs = 30_000

/**
 * Hook do atendimento de uma conversa. Sem `conversationId`, não faz nada.
 *
 * 1. Lê a disponibilidade ao montar e a cada 30 segundos.
 * 2. Com um atendimento na fila ou com a equipe, mantém o fluxo aberto, e
 *    o fecha quando o atendimento termina ou a tela sai.
 *
 * Devolve o retrato, o atendimento ativo e as ações `request`, `send` e
 * `end`.
 */
export function useHandoff(conversationId: string | undefined) {
  const snapshot = useSyncExternalStore(
    subscribeHandoff,
    () => selectHandoff(conversationId),
    () => selectHandoff(conversationId)
  )
  const active = activeHandoff(snapshot)
  const activeId = active?.id ?? null

  // 1.
  useEffect(() => {
    if (!conversationId) {
      return
    }
    let alive = true
    async function refresh() {
      try {
        const result = await api.GET("/v1/handoff/availability")
        if (alive && result.data && conversationId) {
          patchHandoff(conversationId, { availability: result.data.status })
        }
      } catch {
        // Sem rede, a oferta espera a próxima leitura.
      }
    }
    void refresh()
    const timer = window.setInterval(() => void refresh(), availabilityEveryMs)
    return () => {
      alive = false
      window.clearInterval(timer)
    }
  }, [conversationId])

  // 2.
  useEffect(() => {
    if (!conversationId || !activeId) {
      return
    }
    const view = selectHandoff(conversationId).handoffs[activeId]
    const seq = lastSeq(view)
    const stream = openEventStream({
      url: eventsUrl(conversationId),
      lastEventId: seq > 0 ? `${activeId}:${seq}` : null,
      onEvent: (event) => {
        applyEvent(conversationId, activeId, event)
      },
      onState: (state) => {
        patchHandoff(conversationId, { reconnecting: state === "reconnecting" })
      },
    })
    return () => {
      stream.stop()
    }
  }, [conversationId, activeId])

  return {
    ...snapshot,
    active,
    /** Chama a equipe depois da resposta que não ajudou (seção 29.5). */
    request(triggerMessageId: string) {
      if (conversationId) {
        return request(conversationId, triggerMessageId)
      }
      return Promise.resolve(false)
    },
    /** Escreve para a equipe no atendimento ativo. */
    send(text: string) {
      if (conversationId && activeId) {
        return send(conversationId, activeId, text)
      }
      return Promise.resolve(false)
    },
    /** Sai da fila ou encerra o atendimento (FR-24). */
    end() {
      if (conversationId && activeId) {
        void end(conversationId, activeId)
      }
    },
  }
}

/**
 * Pede o atendimento (`POST /v1/conversations/{id}/handoff`).
 *
 * No sucesso, guarda o atendimento, acrescenta o bloco na thread e devolve
 * `true`; o fluxo abre pelo efeito do hook. Os erros da seção 29.10 viram o
 * estado da tela: o bloqueio de 24 horas, a disponibilidade que mudou ou a
 * mensagem da API.
 */
async function request(
  conversationId: string,
  triggerMessageId: string
): Promise<boolean> {
  patchHandoff(conversationId, { requesting: true, error: null })
  try {
    const result = await api.POST(
      "/v1/conversations/{conversation_id}/handoff",
      {
        params: { path: { conversation_id: conversationId } },
        body: { trigger_message_id: triggerMessageId },
      }
    )
    if (result.data) {
      const handoff = result.data
      upsertHandoff(conversationId, handoff.id, {
        status: handoff.status,
        queuePosition: handoff.queue_position,
        closeReason: handoff.close_reason,
        returned: false,
      })
      patchHandoff(conversationId, {
        activeId: handoff.id,
        requesting: false,
        error: null,
      })
      appendHandoffTurn(conversationId, handoff.id)
      return true
    }
    const body = result.error as
      { error?: { code?: string; availability?: string } } | undefined
    const code = body?.error?.code
    if (code === "handoff_blocked") {
      patchHandoff(conversationId, { requesting: false, blocked: true })
      return false
    }
    if (code === "handoff_unavailable") {
      patchHandoff(conversationId, {
        requesting: false,
        availability: availabilityFrom(body?.error?.availability),
      })
      return false
    }
    patchHandoff(conversationId, {
      requesting: false,
      error: messageFrom(result.error, pt.couldNotContinue),
    })
    return false
  } catch {
    patchHandoff(conversationId, {
      requesting: false,
      error: pt.couldNotContinue,
    })
    return false
  }
}

/**
 * Escreve para a equipe. A API devolve a mensagem já sem os
 * identificadores, e a tela mostra o que foi gravado (seção 29.9.7).
 */
async function send(
  conversationId: string,
  handoffId: string,
  text: string
): Promise<boolean> {
  patchHandoff(conversationId, { sending: true, error: null })
  try {
    const result = await api.POST(
      "/v1/conversations/{conversation_id}/handoff/messages",
      {
        params: { path: { conversation_id: conversationId } },
        body: { text, client_message_id: globalThis.crypto.randomUUID() },
      }
    )
    if (result.data) {
      upsertHandoffMessage(conversationId, handoffId, messageView(result.data))
      patchHandoff(conversationId, { sending: false })
      return true
    }
    if (result.response.status === 409) {
      // O atendimento terminou enquanto a pessoa escrevia.
      await refresh(conversationId, handoffId)
    }
    patchHandoff(conversationId, {
      sending: false,
      error: messageFrom(result.error, pt.handoff.sendFailed),
    })
    return false
  } catch {
    patchHandoff(conversationId, {
      sending: false,
      error: pt.handoff.sendFailed,
    })
    return false
  }
}

/** Sai da fila ou encerra o atendimento, com o motivo que a API escolhe. */
async function end(conversationId: string, handoffId: string) {
  patchHandoff(conversationId, { ending: true, error: null })
  try {
    const result = await api.POST(
      "/v1/conversations/{conversation_id}/handoff/end",
      { params: { path: { conversation_id: conversationId } } }
    )
    if (result.data) {
      upsertHandoff(conversationId, handoffId, {
        status: result.data.status,
        queuePosition: result.data.queue_position,
        closeReason: result.data.close_reason,
      })
    }
    patchHandoff(conversationId, { ending: false })
  } catch {
    patchHandoff(conversationId, {
      ending: false,
      error: pt.couldNotContinue,
    })
  }
}

/** Lê o atendimento de novo (`GET /v1/conversations/{id}/handoff`). */
async function refresh(conversationId: string, handoffId: string) {
  const result = await api.GET("/v1/conversations/{conversation_id}/handoff", {
    params: { path: { conversation_id: conversationId } },
  })
  if (result.data && result.data.id === handoffId) {
    upsertHandoff(conversationId, handoffId, {
      status: result.data.status,
      queuePosition: result.data.queue_position,
      closeReason: result.data.close_reason,
    })
  }
}

/**
 * Aplica um evento do fluxo do visitante ao store (seção 29.6).
 *
 * - `ready` e `status` trocam o status, a posição e o motivo. Voltar para a
 *   fila depois de alguém assumir marca `returned`.
 * - `message` põe ou troca a mensagem pelo id.
 * - `reconnect` e `error` são tratados por `openEventStream`.
 */
export function applyEvent(
  conversationId: string,
  handoffId: string,
  event: ServerEvent
) {
  const body = parse(event.data)
  if (event.event === "ready" || event.event === "status") {
    const status = statusFrom(body.status)
    if (!status) {
      return
    }
    const known = selectHandoff(conversationId).handoffs[handoffId]
    upsertHandoff(conversationId, handoffId, {
      status,
      queuePosition:
        typeof body.queue_position === "number" ? body.queue_position : null,
      closeReason:
        typeof body.close_reason === "string" ? body.close_reason : null,
      returned:
        status === "queued" &&
        (known?.status === "assigned" || known?.returned === true),
    })
    return
  }
  if (event.event === "message") {
    const message = messageFromEvent(body)
    if (message) {
      upsertHandoffMessage(conversationId, handoffId, message)
    }
  }
}

/** A mensagem devolvida pelo `POST` no formato do store. */
function messageView(message: {
  id: string
  seq: number
  role: "user" | "attendant"
  content: string
  redaction: string | null
  created_at: string
}): HandoffMessageView {
  return {
    id: message.id,
    seq: message.seq,
    role: message.role,
    content: message.content,
    redaction: message.redaction,
    createdAt: message.created_at,
  }
}

/** A carga de um evento `message`, conferida campo a campo. */
function messageFromEvent(
  body: Record<string, unknown>
): HandoffMessageView | null {
  const { id, seq, role, content, created_at: createdAt } = body
  if (
    typeof id !== "string" ||
    typeof seq !== "number" ||
    (role !== "user" && role !== "attendant") ||
    typeof content !== "string" ||
    typeof createdAt !== "string"
  ) {
    return null
  }
  return {
    id,
    seq,
    role,
    content,
    redaction: typeof body.redaction === "string" ? body.redaction : null,
    createdAt,
  }
}

/** O status do evento, ou `null` fora da lista. */
function statusFrom(value: unknown): HandoffStatus | null {
  return value === "queued" || value === "assigned" || value === "closed"
    ? value
    : null
}

/** A disponibilidade do envelope de erro, ou `closed` fora da lista. */
function availabilityFrom(value: unknown): Availability {
  return value === "open" || value === "busy" || value === "disabled"
    ? value
    : "closed"
}

/** O `data` do evento como objeto. Um texto que não é JSON vira `{}`. */
function parse(data: string): Record<string, unknown> {
  try {
    const parsed: unknown = JSON.parse(data)
    return parsed && typeof parsed === "object"
      ? (parsed as Record<string, unknown>)
      : {}
  } catch {
    return {}
  }
}

/** URL absoluta do fluxo, com o prefixo `/backend` (seção 13.4). */
function eventsUrl(conversationId: string) {
  const origin =
    window.location.origin === "null"
      ? "http://127.0.0.1"
      : window.location.origin
  return `${origin}/backend/v1/conversations/${conversationId}/handoff/events`
}
