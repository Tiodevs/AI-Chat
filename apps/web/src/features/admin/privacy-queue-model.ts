/**
 * Modelo da fila de pedidos de titular do admin: os status, os tipos da
 * resposta da API, o critério do link `mailto:`, os nomes em português e
 * as contagens do topo. Só funções puras, sem React e sem rede.
 *
 * Quem usa: `usePrivacyQueue.ts` e `privacy-queue-screen.tsx`. Usa o `pt`
 * de `i18n/pt.ts`, inclusive os nomes dos tipos de pedido do canal
 * (`pt.privacyRequest.types`).
 *
 * SDD 11.5 (direitos do titular), 12 (`/v1/admin/privacy/requests`) e 15.5
 * (Pedidos de titular).
 */
import { pt } from "@/i18n/pt.ts"

/**
 * Os status de um pedido, na ordem dos botões. `done` e `rejected` fecham o
 * pedido, que não muda mais (SDD 11.5).
 */
export const requestStatuses = ["open", "in_progress", "done", "rejected"] as const
export type RequestStatus = (typeof requestStatuses)[number]

/**
 * Espelha `PrivacyQueueItemResponse` do contrato (SDD 12). `overdue` é
 * calculado pela API: aberto com `due_at` antes de `generated_at`.
 * `linked_account` diz se o pedido veio com sessão de membro e a conta
 * ainda existe.
 */
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

/**
 * Espelha `PrivacyQueueResponse` do contrato (SDD 12): todos os abertos e
 * em andamento, do prazo mais antigo ao mais novo, e depois os 50 fechados
 * mais recentes. `generated_at` é o instante da leitura no servidor.
 */
export type PrivacyQueue = {
  generated_at: string
  requests: PrivacyQueueItem[]
}

/**
 * O teto da nota de resolução, 2.000 caracteres. O servidor decide os
 * limites; aqui só adianta o aviso (SDD 11.5 e 12).
 */
export const resolutionNoteMaxChars = 2000

/**
 * Variante do `Badge` de cada status: em andamento em `--info`, concluído
 * em `--success`, aberto e recusado na superfície neutra (`secondary`).
 */
export const statusVariant = {
  open: "secondary",
  in_progress: "info",
  done: "success",
  rejected: "secondary",
} as const

/**
 * Mesmo critério do servidor (SDD 12): um endereço só, com letras, números
 * e `. _ + -` antes e depois do `@`. Um `?`, uma `,` ou um `;` virariam
 * cabeçalho ou cópia no cliente de e-mail. Fora disso, o contato fica em
 * texto. A tela confere de novo antes de montar o link, sem depender da
 * validação feita quando o pedido chegou.
 */
const safeEmail = /^[a-z0-9._+-]+@[a-z0-9-]+(?:[.][a-z0-9-]+)+$/i

/** O link `mailto:` do contato, ou `null` quando o endereço não é seguro. */
export function mailtoHref(email: string): string | null {
  return safeEmail.test(email) ? `mailto:${email}` : null
}

/** Diz se o status fecha o pedido: `done` ou `rejected`. */
export function isClosed(status: string) {
  return status === "done" || status === "rejected"
}

/**
 * Diz se o status exige nota de resolução. São os mesmos que fecham o
 * pedido: concluir ou recusar exige nota, nova ou já gravada (SDD 11.5).
 */
export function needsNote(status: string) {
  return isClosed(status)
}

/** Nome do status em português. Um status desconhecido aparece cru. */
export function statusLabel(status: string) {
  return (pt.privacyQueue.status as Record<string, string>)[status] ?? status
}

/** Nome do tipo de pedido em português, o mesmo do formulário do canal. */
export function typeLabel(requestType: string) {
  return (pt.privacyRequest.types as Record<string, string>)[requestType] ?? requestType
}

/**
 * As três contagens do topo da fila: atrasados, abertos e em andamento.
 * Elas são completas, porque a API manda todos os pedidos ainda abertos;
 * só os fechados vêm limitados.
 */
export function counts(requests: PrivacyQueueItem[] | undefined) {
  const items = requests ?? []
  return {
    overdue: items.filter((item) => item.overdue).length,
    open: items.filter((item) => item.status === "open").length,
    inProgress: items.filter((item) => item.status === "in_progress").length,
  }
}
