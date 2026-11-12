/**
 * Store do atendimento humano pelo lado do visitante, fora do React. Seções
 * 29.5, 29.6 e 29.11 do SDD.
 *
 * Guarda, por conversa, os atendimentos que a thread mostra (status,
 * posição na fila, motivo do encerramento e mensagens), o atendimento
 * ativo, a disponibilidade e os estados de envio. A thread da IA, em
 * `store.ts`, só sabe onde cada bloco aparece (`HandoffTurn`); o conteúdo
 * mora aqui. Como o store da pergunta, vive no módulo e sobrevive à troca
 * de rota: o fluxo do atendimento continua a escrever aqui.
 *
 * As views leem com `useSyncExternalStore`, em `useHandoff.ts`. Cada
 * escrita cria um retrato novo e chama `emit`. Usado também por
 * `useAskConversation.ts`, que semeia os atendimentos ao ler a conversa, e
 * por `src/test/setup.ts` e `useSignOut`, que limpam tudo.
 */
import type { StoredHandoff, StoredMessage } from "./types.ts"

/** Status do atendimento (seção 29.5). */
export type HandoffStatus = "queued" | "assigned" | "closed"

/** O status único da disponibilidade (seção 29.4). */
export type Availability = "open" | "busy" | "closed" | "disabled"

/** Uma mensagem do atendimento, como a API a gravou, já com os marcadores. */
export type HandoffMessageView = {
  id: string
  /** O cursor da retomada. Uma remoção dá à mensagem um `seq` novo. */
  seq: number
  /** `user` é o visitante; `attendant`, a equipe. */
  role: "user" | "attendant"
  content: string
  /** A categoria da remoção, ou `retention` quando a regra de 90 dias apagou. */
  redaction: string | null
  createdAt: string
}

/** Um atendimento da conversa, com as mensagens em ordem. */
export type HandoffView = {
  id: string
  status: HandoffStatus
  queuePosition: number | null
  closeReason: string | null
  /** Voltou para a fila depois de alguém assumir (seção 29.5, passo 6). */
  returned: boolean
  messages: HandoffMessageView[]
}

/** O retrato do atendimento de uma conversa. */
export type HandoffSnapshot = {
  handoffs: Record<string, HandoffView>
  /** O atendimento mais novo da conversa, ativo ou o último encerrado. */
  activeId: string | null
  availability: Availability | null
  /** Encerramento por abuso nas últimas 24 horas (seção 29.4). */
  blocked: boolean
  /** O fluxo caiu há mais de 5 segundos (seção 29.11). */
  reconnecting: boolean
  requesting: boolean
  sending: boolean
  ending: boolean
  /** Erro do pedido, do envio ou do encerramento, já em português. */
  error: string | null
}

const listeners = new Set<() => void>()
const entries = new Map<string, HandoffSnapshot>()
/** O retrato de uma conversa sem atendimento: o mesmo objeto até mudar. */
let empty = blank()

/** Registra um ouvinte para o `useSyncExternalStore` e devolve quem o tira. */
export function subscribeHandoff(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/** O retrato da conversa, com a mesma referência enquanto nada mudou. */
export function selectHandoff(
  conversationId: string | undefined
): HandoffSnapshot {
  if (!conversationId) {
    return empty
  }
  return entries.get(conversationId) ?? empty
}

/** O atendimento ativo, na fila ou com alguém da equipe, ou `null`. */
export function activeHandoff(snapshot: HandoffSnapshot): HandoffView | null {
  const current = snapshot.activeId
    ? snapshot.handoffs[snapshot.activeId]
    : undefined
  if (!current || current.status === "closed") {
    return null
  }
  return current
}

/** Mescla campos no retrato da conversa e avisa os ouvintes. */
export function patchHandoff(
  conversationId: string,
  partial: Partial<HandoffSnapshot>
) {
  entries.set(conversationId, { ...selectHandoff(conversationId), ...partial })
  emit()
}

/**
 * Semeia os atendimentos lidos com a conversa (`GET /v1/conversations/{id}`).
 *
 * As mensagens com `handoff_id` vão para o atendimento delas, em ordem. O
 * mais novo vira o `activeId`. Um atendimento que o fluxo já trouxe fica
 * com o que tem de mais novo.
 */
export function seedHandoffs(
  conversationId: string,
  handoffs: StoredHandoff[],
  messages: StoredMessage[]
) {
  const current = selectHandoff(conversationId)
  const next: Record<string, HandoffView> = { ...current.handoffs }
  for (const handoff of handoffs) {
    const known = next[handoff.id]
    const stored = messages
      .filter((message) => message.handoffId === handoff.id)
      .map(storedMessage)
    next[handoff.id] = {
      id: handoff.id,
      status: known?.status ?? handoff.status,
      queuePosition: known?.queuePosition ?? null,
      closeReason: known?.closeReason ?? handoff.closeReason,
      returned: known?.returned ?? false,
      messages: mergeMessages(known?.messages ?? [], stored),
    }
  }
  const latest = [...handoffs].sort(
    (first, second) =>
      Date.parse(second.requestedAt) - Date.parse(first.requestedAt)
  )[0]
  patchHandoff(conversationId, {
    handoffs: next,
    activeId: current.activeId ?? latest?.id ?? null,
  })
}

/** Grava os campos de um atendimento, criando-o se ainda não existe. */
export function upsertHandoff(
  conversationId: string,
  handoffId: string,
  partial: Partial<Omit<HandoffView, "id" | "messages">>
) {
  const current = selectHandoff(conversationId)
  const known = current.handoffs[handoffId] ?? {
    id: handoffId,
    status: "queued" as const,
    queuePosition: null,
    closeReason: null,
    returned: false,
    messages: [],
  }
  patchHandoff(conversationId, {
    handoffs: { ...current.handoffs, [handoffId]: { ...known, ...partial } },
  })
}

/**
 * Põe uma mensagem no atendimento, trocando a de mesmo id. Assim, uma
 * remoção que chega depois só troca o texto, e a mensagem devolvida pelo
 * `POST` e a do fluxo não aparecem duas vezes (seção 29.6).
 */
export function upsertHandoffMessage(
  conversationId: string,
  handoffId: string,
  message: HandoffMessageView
) {
  const current = selectHandoff(conversationId)
  const known = current.handoffs[handoffId]
  if (!known) {
    return
  }
  patchHandoff(conversationId, {
    handoffs: {
      ...current.handoffs,
      [handoffId]: {
        ...known,
        messages: mergeMessages(known.messages, [message]),
      },
    },
  })
}

/** O maior `seq` já visto do atendimento, para o `Last-Event-ID`. */
export function lastSeq(view: HandoffView | undefined): number {
  return Math.max(0, ...(view?.messages.map((message) => message.seq) ?? []))
}

/** Esquece todos os atendimentos. Na saída da conta e depois de cada teste. */
export function resetHandoffState() {
  entries.clear()
  empty = blank()
  emit()
}

/**
 * Junta as mensagens pelo id: a versão de `seq` maior vence, e a lista sai
 * na ordem de gravação.
 */
function mergeMessages(
  known: HandoffMessageView[],
  incoming: HandoffMessageView[]
): HandoffMessageView[] {
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

/** A mensagem gravada no formato do atendimento. */
function storedMessage(message: StoredMessage): HandoffMessageView {
  return {
    id: message.id,
    seq: 0,
    role: message.role === "attendant" ? "attendant" : "user",
    content: message.content,
    redaction: message.redaction,
    createdAt: message.createdAt,
  }
}

/** Um retrato vazio. */
function blank(): HandoffSnapshot {
  return {
    handoffs: {},
    activeId: null,
    availability: null,
    blocked: false,
    reconnecting: false,
    requesting: false,
    sending: false,
    ending: false,
    error: null,
  }
}

/** Avisa quem assina o store. */
function emit() {
  for (const listener of listeners) {
    listener()
  }
}
