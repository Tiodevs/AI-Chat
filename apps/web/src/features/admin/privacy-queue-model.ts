import { pt } from "@/i18n/pt.ts"

export const requestStatuses = ["open", "in_progress", "done", "rejected"] as const
export type RequestStatus = (typeof requestStatuses)[number]

/** Espelha `PrivacyQueueItemResponse` do contrato (SDD 12). */
export type PrivacyQueueItem = {
  id: string
  request_type: string
  status: string
  contact_email: string
  description: string
  received_at: string
  due_at: string
  closed_at: string | null
  resolution_note: string | null
  overdue: boolean
  linked_account: boolean
}

/** Espelha `PrivacyQueueResponse` do contrato (SDD 12). */
export type PrivacyQueue = {
  generated_at: string
  requests: PrivacyQueueItem[]
}

/** O servidor decide os limites; aqui só adianta o aviso (SDD 11.5). */
export const resolutionNoteMaxChars = 2000

export const statusVariant = {
  open: "secondary",
  in_progress: "info",
  done: "success",
  rejected: "secondary",
} as const

/** Mesmo critério do servidor (SDD 12): um endereço só, sem `?`, `,` ou `;` que um
 * cliente de e-mail trataria como cabeçalho ou cópia. Fora disso, o contato fica em texto. */
const safeEmail = /^[a-z0-9._+-]+@[a-z0-9-]+(?:[.][a-z0-9-]+)+$/i

export function mailtoHref(email: string): string | null {
  return safeEmail.test(email) ? `mailto:${email}` : null
}

export function isClosed(status: string) {
  return status === "done" || status === "rejected"
}

export function needsNote(status: string) {
  return isClosed(status)
}

export function statusLabel(status: string) {
  return (pt.privacyQueue.status as Record<string, string>)[status] ?? status
}

export function typeLabel(requestType: string) {
  return (pt.privacyRequest.types as Record<string, string>)[requestType] ?? requestType
}

export function counts(requests: PrivacyQueueItem[] | undefined) {
  const items = requests ?? []
  return {
    overdue: items.filter((item) => item.overdue).length,
    open: items.filter((item) => item.status === "open").length,
    inProgress: items.filter((item) => item.status === "in_progress").length,
  }
}
