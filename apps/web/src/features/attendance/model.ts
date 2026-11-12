/**
 * Tipos e conversões do console de atendimento. Seções 29.6, 29.9.4 e 29.10.
 *
 * Funções puras: convertem as respostas da API nos tipos das views e
 * calculam o título da aba. Quem usa: `useAttendance.ts`,
 * `useClosedHandoffs.ts` e as telas desta pasta. Os textos vêm de
 * `src/i18n/pt.ts`.
 */
import type {
  ThreadLine,
  ThreadMessage,
} from "@/components/patterns/handoff-thread.tsx"
import type { QueueItemView } from "@/components/patterns/queue-list.tsx"
import { pt } from "@/i18n/pt.ts"

// As formas das respostas da API que esta pasta lê, copiadas do OpenAPI
// (`StaffHandoffResponse`, `HandoffMessageResponse` e
// `HandoffDetailResponse`). Só os hooks importam `schema.ts` (seção 6.2), e o
// `tsc` confere que o que eles passam cabe aqui.

/** Um atendimento na fila ou na aba, sem conteúdo. */
export type ApiStaffHandoff = {
  handoff_id: string
  label: string
  status: "queued" | "assigned" | "closed"
  trigger: string
  queued_at: string
  close_reason: string | null
  visitor_present: boolean
}

/** Uma mensagem do atendimento. */
export type ApiMessage = {
  id: string
  seq: number
  role: "user" | "attendant"
  content: string
  redaction: string | null
  created_at: string
}

/** O atendimento e a conversa da seção 29.9.4. */
export type ApiDetail = {
  handoff: ApiStaffHandoff
  conversation: {
    id: string
    role: "user" | "assistant"
    content: string
    outcome: string | null
    citations: {
      index: number
      document_title: string
      heading: string | null
    }[]
  }[]
  messages: ApiMessage[]
}

/** Um atendimento da pessoa, como a aba o mostra. */
export type StaffHandoffView = {
  id: string
  label: string
  status: "queued" | "assigned" | "closed"
  trigger: string
  queuedAt: string
  closeReason: string | null
  visitorPresent: boolean
}

/** Uma mensagem do atendimento, com o `seq` da retomada. */
export type StaffMessageView = ThreadMessage & {
  seq: number
  createdAt: string
}

/** O atendimento aberto numa aba: o resumo, a conversa e as mensagens. */
export type DetailView = {
  handoff: StaffHandoffView
  conversation: ThreadLine[]
  messages: StaffMessageView[]
}

/** O item da fila, sem conteúdo (seção 29.9.4). */
export function queueItem(item: {
  handoff_id: string
  label: string
  queued_at: string
  trigger: string
  returned: boolean
  visitor_present: boolean
}): QueueItemView {
  return {
    handoffId: item.handoff_id,
    label: item.label,
    queuedAt: item.queued_at,
    trigger: item.trigger,
    returned: item.returned,
    visitorPresent: item.visitor_present,
  }
}

/** O resumo do atendimento no formato da aba. */
export function staffHandoff(item: ApiStaffHandoff): StaffHandoffView {
  return {
    id: item.handoff_id,
    label: item.label,
    status: item.status,
    trigger: item.trigger,
    queuedAt: item.queued_at,
    closeReason: item.close_reason,
    visitorPresent: item.visitor_present,
  }
}

/** Uma mensagem do atendimento no formato da aba. */
export function staffMessage(message: ApiMessage): StaffMessageView {
  return {
    id: message.id,
    seq: message.seq,
    role: message.role,
    content: message.content,
    redaction: message.redaction,
    createdAt: message.created_at,
  }
}

/** O atendimento com a conversa, como a seção 29.9.4 define. */
export function detailView(detail: ApiDetail): DetailView {
  return {
    handoff: staffHandoff(detail.handoff),
    conversation: detail.conversation.map((line) => ({
      id: line.id,
      role: line.role,
      content: line.content,
      outcome: line.outcome,
      citations: line.citations.map((citation) => ({
        index: citation.index,
        documentTitle: citation.document_title,
        heading: citation.heading,
      })),
    })),
    messages: detail.messages.map(staffMessage),
  }
}

/**
 * Junta mensagens pelo id: a de `seq` maior vence, e a lista sai na ordem
 * de gravação. Uma remoção que chega pelo fluxo só troca o texto.
 */
export function mergeMessages(
  known: StaffMessageView[],
  incoming: StaffMessageView[]
): StaffMessageView[] {
  const byId = new Map(known.map((message) => [message.id, message]))
  for (const message of incoming) {
    const previous = byId.get(message.id)
    if (!previous || previous.seq <= message.seq) {
      byId.set(message.id, message)
    }
  }
  return [...byId.values()].sort(
    (first, second) =>
      Date.parse(first.createdAt) - Date.parse(second.createdAt) ||
      first.seq - second.seq
  )
}

/**
 * O título da aba do console, só com a contagem de novidades e nunca com
 * conteúdo (seção 29.9.4). Sem novidade, volta ao título da página.
 */
export function consoleTitle(count: number): string {
  if (count <= 0) {
    return `${pt.pages.attendance} · ${pt.appName}`
  }
  return pt.attendance.titleCount.replace("{count}", String(count))
}

/** A duração entre dois instantes, em minutos, para a lista do admin. */
export function minutesBetween(
  start: string | null,
  end: string | null
): string {
  if (!start || !end) {
    return "—"
  }
  const minutes = Math.max(
    0,
    Math.round((Date.parse(end) - Date.parse(start)) / 60_000)
  )
  return minutes === 1
    ? pt.attendance.minutesOne
    : pt.attendance.minutesMany.replace("{minutes}", String(minutes))
}
