/**
 * Controlador do console de atendimento: presença, fila, abas, ações e o
 * fluxo em tempo real. Seções 29.3, 29.5, 29.6 e 29.11 do SDD.
 *
 * Usado por `app/routes/attendance.tsx` e `attendance-commitment.tsx`. Usa o
 * cliente tipado (`lib/api/client.ts`) e `openEventStream`, de `lib/sse.ts`,
 * para `GET /v1/attendance/events`. O estado vive neste módulo, fora do
 * React, como o da conversa: as views leem com `useSyncExternalStore`.
 *
 * Na retomada, o console lê de novo a fila e cada atendimento aberto com
 * `after_seq`, porque o fluxo dele mistura vários atendimentos (seção
 * 29.6). A fila nunca traz conteúdo; o conteúdo só chega para quem assumiu.
 */
import { useEffect, useSyncExternalStore } from "react"

import type { PresenceValue } from "@/components/patterns/presence-toggle.tsx"
import type { QueueItemView } from "@/components/patterns/queue-list.tsx"
import type { RedactCategory } from "@/components/patterns/redact-dialog.tsx"
import { messageFrom } from "@/features/auth/api-error.ts"
import { pt } from "@/i18n/pt.ts"
import { api } from "@/lib/api/client.ts"
import {
  openEventStream,
  type ServerEvent,
  type StreamState,
} from "@/lib/sse.ts"

import {
  detailView,
  mergeMessages,
  queueItem,
  staffMessage,
  type DetailView,
} from "./model.ts"

/** O retrato do console. */
export type ConsoleSnapshot = {
  presence: PresenceValue
  acknowledged: boolean | null
  termsVersion: string | null
  queue: QueueItemView[]
  availableAttendants: number
  /** Os atendimentos da pessoa, na ordem em que foram assumidos. */
  mine: string[]
  details: Record<string, DetailView>
  /** A aba aberta. */
  selected: string | null
  /** Mensagens do visitante ainda não vistas, por atendimento. */
  unread: Record<string, number>
  connection: StreamState | "idle"
  /** Um aviso passageiro, como "Outra pessoa já assumiu". */
  notice: string | null
  takingId: string | null
  busy: boolean
  loaded: boolean
}

/** O que `take` devolve: assumiu, precisa do compromisso ou não deu. */
export type TakeResult = "taken" | "commitment" | "failed"

const listeners = new Set<() => void>()
let state = blank()

/**
 * Hook do console. Lê o estado com `useSyncExternalStore` e, enquanto
 * monta, mantém o fluxo do console aberto. Devolve o retrato e as ações.
 */
export function useAttendance({ stream = true }: { stream?: boolean } = {}) {
  const snapshot = useSyncExternalStore(
    subscribe,
    () => state,
    () => state
  )

  useEffect(() => {
    void loadConsole()
    if (!stream) {
      return
    }
    let opened = false
    const connection = openEventStream({
      url: eventsUrl(),
      onEvent: applyEvent,
      onState: (next) => {
        patch({ connection: next })
        // Na retomada, a fila e as abas são lidas de novo (seção 29.6).
        if (next === "open" && opened) {
          void loadConsole()
        }
        opened = opened || next === "open"
      },
    })
    return () => {
      connection.stop()
    }
  }, [stream])

  return {
    ...snapshot,
    setPresence,
    acknowledge,
    take,
    send,
    sendEmergency,
    release,
    close,
    redact,
    select(handoffId: string) {
      patch({
        selected: handoffId,
        unread: { ...state.unread, [handoffId]: 0 },
      })
    },
    dismissNotice() {
      patch({ notice: null })
    },
  }
}

/** Lê a presença, o aceite, a fila e cada atendimento da pessoa. */
export async function loadConsole() {
  try {
    const [me, queue] = await Promise.all([
      api.GET("/v1/attendance/me"),
      api.GET("/v1/attendance/queue"),
    ])
    if (me.data) {
      patch({
        presence: me.data.presence,
        acknowledged: me.data.acknowledged,
        termsVersion: me.data.terms_version,
      })
    }
    if (!queue.data) {
      patch({ loaded: true })
      return
    }
    const mine = queue.data.mine.map((item) => item.handoff_id)
    patch({
      queue: queue.data.queued.map(queueItem),
      availableAttendants: queue.data.available_attendants,
      mine,
      selected:
        state.selected && mine.includes(state.selected)
          ? state.selected
          : (mine[0] ?? null),
      loaded: true,
    })
    await Promise.all(mine.map((handoffId) => loadDetail(handoffId)))
  } catch {
    patch({ loaded: true, notice: pt.couldNotContinue })
  }
}

/** Lê um atendimento da pessoa e o guarda na aba. */
async function loadDetail(handoffId: string) {
  const result = await api.GET("/v1/attendance/handoffs/{handoff_id}", {
    params: { path: { handoff_id: handoffId } },
  })
  if (result.data) {
    const view = detailView(result.data)
    const known = state.details[handoffId]
    patch({
      details: {
        ...state.details,
        [handoffId]: known
          ? { ...view, messages: mergeMessages(known.messages, view.messages) }
          : view,
      },
    })
  }
}

/**
 * Marca Disponível ou Ausente (`PUT /v1/attendance/presence`) e lê a fila
 * de novo, para Equipe disponível já contar a mudança sem esperar o tique.
 */
async function setPresence(status: PresenceValue) {
  const previous = state.presence
  patch({ presence: status, busy: true })
  try {
    const result = await api.PUT("/v1/attendance/presence", {
      body: { status },
    })
    patch({ busy: false, presence: result.data?.presence ?? previous })
    const queue = await api.GET("/v1/attendance/queue")
    if (queue.data) {
      patch({
        queue: queue.data.queued.map(queueItem),
        availableAttendants: queue.data.available_attendants,
      })
    }
  } catch {
    patch({
      busy: false,
      presence: previous,
      notice: pt.attendance.actionFailed,
    })
  }
}

/** Aceita o compromisso vigente. Devolve se o aceite foi gravado. */
async function acknowledge(): Promise<boolean> {
  const version = state.termsVersion
  if (!version) {
    await loadConsole()
  }
  const current = state.termsVersion
  if (!current) {
    return false
  }
  patch({ busy: true })
  try {
    const result = await api.POST("/v1/attendance/acknowledgement", {
      body: { version: current },
    })
    patch({ busy: false, acknowledged: result.data?.acknowledged ?? false })
    return result.data?.acknowledged ?? false
  } catch {
    patch({ busy: false, notice: pt.attendance.actionFailed })
    return false
  }
}

/**
 * Assume um atendimento da fila (seção 29.5, passo 4). Sem o aceite
 * vigente, devolve `commitment`, e a tela leva ao compromisso (seção 29.3).
 * Outra pessoa primeiro: o aviso da seção 29.11 e a fila de novo.
 */
async function take(handoffId: string): Promise<TakeResult> {
  patch({ takingId: handoffId, notice: null })
  try {
    const result = await api.POST("/v1/attendance/handoffs/{handoff_id}/take", {
      params: { path: { handoff_id: handoffId } },
    })
    if (result.data) {
      const view = detailView(result.data)
      patch({
        takingId: null,
        details: { ...state.details, [handoffId]: view },
        mine: state.mine.includes(handoffId)
          ? state.mine
          : [...state.mine, handoffId],
        selected: handoffId,
        queue: state.queue.filter((item) => item.handoffId !== handoffId),
      })
      return "taken"
    }
    const code = errorCode(result.error)
    patch({ takingId: null })
    if (code === "acknowledgement_required") {
      return "commitment"
    }
    patch({
      notice:
        code === "handoff_taken"
          ? pt.attendance.taken
          : code === "attendant_at_capacity"
            ? pt.attendance.atCapacity
            : messageFrom(result.error, pt.attendance.actionFailed),
    })
    await loadConsole()
    return "failed"
  } catch {
    patch({ takingId: null, notice: pt.attendance.actionFailed })
    return "failed"
  }
}

/** Responde ao visitante. Devolve se a mensagem foi gravada. */
async function send(handoffId: string, text: string): Promise<boolean> {
  return postMessage(handoffId, { text })
}

/** Manda o texto fixo de orientação médica da seção 10.1. */
async function sendEmergency(handoffId: string): Promise<boolean> {
  return postMessage(handoffId, { template: "medical_emergency" })
}

async function postMessage(
  handoffId: string,
  body: { text?: string; template?: "medical_emergency" }
): Promise<boolean> {
  patch({ busy: true })
  try {
    const result = await api.POST(
      "/v1/attendance/handoffs/{handoff_id}/messages",
      {
        params: { path: { handoff_id: handoffId } },
        body: { ...body, client_message_id: globalThis.crypto.randomUUID() },
      }
    )
    patch({ busy: false })
    if (result.data) {
      upsertMessage(handoffId, staffMessage(result.data))
      return true
    }
    patch({ notice: messageFrom(result.error, pt.attendance.actionFailed) })
    if (result.response.status === 404 || result.response.status === 409) {
      await loadConsole()
    }
    return false
  } catch {
    patch({ busy: false, notice: pt.attendance.actionFailed })
    return false
  }
}

/** Devolve o atendimento à fila e fecha a aba. */
async function release(handoffId: string) {
  await finish(handoffId, () =>
    api.POST("/v1/attendance/handoffs/{handoff_id}/release", {
      params: { path: { handoff_id: handoffId } },
    })
  )
}

/** Encerra com um motivo da lista fechada e fecha a aba. */
async function close(handoffId: string, reason: string) {
  await finish(handoffId, () =>
    api.POST("/v1/attendance/handoffs/{handoff_id}/close", {
      params: { path: { handoff_id: handoffId } },
      body: { reason },
    })
  )
}

/** Remove o conteúdo de uma mensagem do atendimento, com a categoria. */
async function redact(
  handoffId: string,
  messageId: string,
  category: RedactCategory
) {
  patch({ busy: true })
  try {
    const result = await api.POST(
      "/v1/attendance/handoffs/{handoff_id}/messages/{message_id}/redact",
      {
        params: { path: { handoff_id: handoffId, message_id: messageId } },
        body: { category },
      }
    )
    patch({ busy: false })
    if (result.data) {
      upsertMessage(handoffId, staffMessage(result.data))
      return true
    }
    patch({ notice: messageFrom(result.error, pt.attendance.actionFailed) })
    return false
  } catch {
    patch({ busy: false, notice: pt.attendance.actionFailed })
    return false
  }
}

/** Uma ação que tira o atendimento da pessoa: no sucesso, a aba some. */
async function finish(
  handoffId: string,
  call: () => Promise<{ data?: unknown; error?: unknown }>
) {
  patch({ busy: true })
  try {
    const result = await call()
    patch({ busy: false })
    if (result.data) {
      removeTab(handoffId)
      return
    }
    patch({ notice: messageFrom(result.error, pt.attendance.actionFailed) })
  } catch {
    patch({ busy: false, notice: pt.attendance.actionFailed })
  }
}

/**
 * Aplica um evento do fluxo do console ao store (seção 29.6).
 *
 * - `ready`: a presença e o aceite.
 * - `queue`: a fila inteira, sem conteúdo, e a equipe disponível.
 * - `assigned`: assumido em outra aba; o console lê o atendimento.
 * - `message`: põe ou troca a mensagem e conta a novidade.
 * - `status`: o visitante entrou ou saiu da conversa, ou o atendimento
 *   terminou; encerrado, a aba some com o aviso.
 * - `removed`: a conversa sumiu ou passou para outra pessoa.
 */
export function applyEvent(event: ServerEvent) {
  const body = parse(event.data)
  if (event.event === "ready") {
    patch({
      presence: body.presence === "available" ? "available" : "away",
      acknowledged: body.acknowledged === true,
    })
    return
  }
  if (event.event === "queue") {
    const queued = Array.isArray(body.queued) ? body.queued : []
    patch({
      queue: queued.filter(isQueueItem).map(queueItem),
      availableAttendants:
        typeof body.available_attendants === "number"
          ? body.available_attendants
          : 0,
    })
    return
  }
  const handoffId = typeof body.handoff_id === "string" ? body.handoff_id : null
  if (!handoffId) {
    return
  }
  if (event.event === "assigned") {
    if (!state.mine.includes(handoffId)) {
      patch({
        mine: [...state.mine, handoffId],
        selected: state.selected ?? handoffId,
      })
    }
    void loadDetail(handoffId)
    return
  }
  if (event.event === "message") {
    const message = messageFromEvent(body)
    if (message) {
      const fresh = !state.details[handoffId]?.messages.some(
        (item) => item.id === message.id
      )
      upsertMessage(handoffId, message)
      const unseen =
        message.role === "user" &&
        fresh &&
        (state.selected !== handoffId || document.visibilityState === "hidden")
      if (unseen) {
        patch({
          unread: {
            ...state.unread,
            [handoffId]: (state.unread[handoffId] ?? 0) + 1,
          },
        })
      }
    }
    return
  }
  if (event.event === "status") {
    if (body.status === "closed") {
      removeTab(handoffId)
      patch({ notice: pt.attendance.statusClosed })
      return
    }
    const detail = state.details[handoffId]
    if (detail) {
      patch({
        details: {
          ...state.details,
          [handoffId]: {
            ...detail,
            handoff: {
              ...detail.handoff,
              visitorPresent: body.visitor_present === true,
            },
          },
        },
      })
    }
    return
  }
  if (event.event === "removed") {
    removeTab(handoffId)
  }
}

/** O retrato atual do console, fora do React. Serve aos testes. */
export function selectConsole(): ConsoleSnapshot {
  return state
}

/** Esquece o estado do console. Na saída da conta e depois de cada teste. */
export function resetAttendanceState() {
  state = blank()
  emit()
}

/** Põe a mensagem na aba, trocando a de mesmo id. */
function upsertMessage(
  handoffId: string,
  message: DetailView["messages"][number]
) {
  const detail = state.details[handoffId]
  if (!detail) {
    return
  }
  patch({
    details: {
      ...state.details,
      [handoffId]: {
        ...detail,
        messages: mergeMessages(detail.messages, [message]),
      },
    },
  })
}

/** Tira o atendimento das abas da pessoa. */
function removeTab(handoffId: string) {
  const mine = state.mine.filter((item) => item !== handoffId)
  const details = { ...state.details }
  delete details[handoffId]
  const unread = { ...state.unread }
  delete unread[handoffId]
  patch({
    mine,
    details,
    unread,
    selected: state.selected === handoffId ? (mine[0] ?? null) : state.selected,
  })
}

function isQueueItem(value: unknown): value is {
  handoff_id: string
  label: string
  queued_at: string
  trigger: string
  returned: boolean
  visitor_present: boolean
} {
  if (!value || typeof value !== "object") {
    return false
  }
  const item = value as Record<string, unknown>
  return (
    typeof item.handoff_id === "string" &&
    typeof item.label === "string" &&
    typeof item.queued_at === "string" &&
    typeof item.trigger === "string"
  )
}

function messageFromEvent(body: Record<string, unknown>) {
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
  } as const
}

function errorCode(error: unknown): string | null {
  const body = error as { error?: { code?: unknown } } | undefined
  return typeof body?.error?.code === "string" ? body.error.code : null
}

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

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

function patch(partial: Partial<ConsoleSnapshot>) {
  state = { ...state, ...partial }
  emit()
}

function emit() {
  for (const listener of listeners) {
    listener()
  }
}

function blank(): ConsoleSnapshot {
  return {
    presence: "away",
    acknowledged: null,
    termsVersion: null,
    queue: [],
    availableAttendants: 0,
    mine: [],
    details: {},
    selected: null,
    unread: {},
    connection: "idle",
    notice: null,
    takingId: null,
    busy: false,
    loaded: false,
  }
}

/** URL absoluta do fluxo do console, com o prefixo `/backend`. */
function eventsUrl() {
  const origin =
    window.location.origin === "null"
      ? "http://127.0.0.1"
      : window.location.origin
  return `${origin}/backend/v1/attendance/events`
}
