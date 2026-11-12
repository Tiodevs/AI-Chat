/**
 * Regras puras da conversa: como cada evento SSE muda o turno do
 * assistente, como as mensagens gravadas viram turnos e o que a região ao
 * vivo anuncia. Seções 7.1, 15.5 e 15.8 do SDD.
 *
 * Não faz pedido nem guarda estado: recebe um valor e devolve outro, e por
 * isso é testado sem rede em `model.test.ts`. Quem chama é
 * `useAskConversation.ts`; `store.ts` usa `syncPrivacy` e `announcementFor`
 * a cada escrita. Os textos vêm de `src/i18n/pt.ts`.
 */
import { pt } from "@/i18n/pt.ts"

import {
  HEALTH_MARKER,
  type AssistantTurn,
  type CitationView,
  type StoredHandoff,
  type StoredMessage,
  type Turn,
  type UserTurn,
} from "./types.ts"

/**
 * Texto do limite de perguntas (seção 15.5, Limite de taxa).
 *
 * Arredonda `retry_after_seconds` para cima, em minutos, com mínimo de 1:
 * 30 segundos viram 1 minuto, e 90 viram 2 minutos.
 */
export function questionLimit(retryAfterSeconds: number): string {
  const minutes = Math.max(1, Math.ceil(retryAfterSeconds / 60))
  if (minutes === 1) {
    return pt.ask.limitedOne
  }
  return pt.ask.limitedMany.replace("{minutes}", String(minutes))
}

/**
 * Converte as mensagens gravadas em turnos da thread, na ordem do banco.
 *
 * - A pergunta gravada com o `HEALTH_MARKER` vira um turno com `privacy` e
 *   sem texto (seção 7.1, passo 8).
 * - A resposta com desfecho `cancelled` volta como Interrompida, com a
 *   pergunta anterior em `retryText`, para o Tentar de novo.
 * - O banco não devolve o `request_id` nem a avaliação, então os dois
 *   começam vazios. Avaliar de novo recebe 409 e vira `"locked"`.
 * - As mensagens do atendimento humano saem da conversa com a IA. Cada
 *   atendimento entra como um `HandoffTurn`, no ponto do pedido: depois das
 *   mensagens gravadas antes dele (seção 29.11).
 */
export function turnsFromStored(
  messages: StoredMessage[],
  handoffs: StoredHandoff[] = []
): Turn[] {
  const turns: Turn[] = []
  let lastUserText: string | null = null
  const blocks = [...handoffs].sort(
    (first, second) =>
      Date.parse(first.requestedAt) - Date.parse(second.requestedAt)
  )
  let next = 0
  for (const message of messages) {
    if (message.handoffId || message.role === "attendant") {
      continue
    }
    // Os atendimentos pedidos antes desta mensagem vêm antes dela.
    while (
      next < blocks.length &&
      Date.parse(blocks[next]?.requestedAt ?? "") <=
        Date.parse(message.createdAt)
    ) {
      const block = blocks[next]
      if (block) {
        turns.push({ key: block.id, role: "handoff", handoffId: block.id })
      }
      next += 1
    }
    if (message.role === "user") {
      const privacy = message.content === HEALTH_MARKER
      // O texto da pergunta médica não está no banco: não há o que repetir.
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
      // A API grava a resposta uma vez, já com o desfecho (seção 7.1,
      // transação 2). Sem desfecho, o turno fica em espera.
      phase: cancelled ? "cancelled" : message.outcome ? "done" : "waiting",
      replaced: false,
      errorMessage: null,
      feedback: null,
      retryText: cancelled ? lastUserText : null,
    }
    turns.push(assistant)
  }
  for (const block of blocks.slice(next)) {
    turns.push({ key: block.id, role: "handoff", handoffId: block.id })
  }
  return turns
}

/**
 * Desfechos que oferecem o atendimento logo depois da resposta (seção
 * 29.4). `answered` só com a nota não útil; `refused` e `cancelled`
 * nunca.
 */
const offerOutcomes = new Set([
  "abstained",
  "grounding_failed",
  "off_topic",
  "degraded",
  "error",
])

/**
 * A resposta que motiva a oferta do atendimento, ou `null` (FR-19).
 *
 * Só a última resposta da thread conta, e só quando ela é o último item:
 * depois de um atendimento, a oferta espera uma resposta nova do Atrium. A
 * regra é a mesma de `handoff_offer`, em `apps/api/app/domain/handoff.py`;
 * a API confere de novo no pedido.
 */
export function offerAnswer(messages: Turn[]): AssistantTurn | null {
  const last = messages[messages.length - 1]
  if (last?.role !== "assistant" || last.phase !== "done" || !last.id) {
    return null
  }
  if (last.outcome && offerOutcomes.has(last.outcome)) {
    return last
  }
  if (last.outcome === "answered" && last.feedback === -1) {
    return last
  }
  return null
}

/**
 * Aplica um evento SSE ao turno do assistente e devolve um turno novo.
 *
 * É o redutor do fluxo de `POST /v1/conversations/{id}/messages`, com os
 * eventos da tabela da seção 7.1:
 * - `meta` traz o id da mensagem e o `request_id`; a fase não muda.
 * - `token` acrescenta texto e passa a fase para `streaming`.
 * - `replace` troca o rascunho pela resposta segura e limpa as citações.
 * - `citation` acrescenta uma fonte.
 * - `done` grava o desfecho e encerra o turno.
 * - `error` encerra o turno com a mensagem do servidor.
 *
 * Um evento desconhecido devolve o turno igual. Um `data` que não é JSON
 * faz `JSON.parse` lançar, e `submit` trata isso como fluxo quebrado.
 */
export function applyStreamEvent(
  turn: AssistantTurn,
  event: { event: string; data: string }
): AssistantTurn {
  const body = readPayload(event.data)
  if (event.event === "meta") {
    // O `message_id` é o id que o feedback usa. Sem token, a tela segue
    // com o skeleton (seção 15.5, Aguardando o primeiro token).
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
    // O rascunho vai para `outgoing`, que a M9 anima na saída (seção
    // 16.3). A fase fica em `streaming` até o `done`, e o anúncio espera.
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
    // Uma citação incompleta é ignorada, sem quebrar o fluxo.
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
    // O evento substitui o `done` quando o fluxo quebra depois do `meta`
    // (seção 7.1). O texto parcial sai, e fica a mensagem.
    return {
      ...turn,
      phase: "error",
      text: "",
      errorMessage: textField(body, "message") ?? pt.ask.couldNotFinish,
    }
  }
  return turn
}

/**
 * Marca como `privacy` a pergunta seguida de uma recusa médica (`refused`).
 *
 * Durante o fluxo, o texto da pergunta está na memória. Quando o `done`
 * traz `refused`, a view troca o texto pela nota de privacidade, como faz
 * com a pergunta gravada com o marcador (seção 15.5, Recusa médica). O
 * texto continua no turno em memória; só a view deixa de mostrá-lo.
 * Devolve o mesmo objeto para cada turno que não muda.
 */
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

/**
 * Texto que a região `aria-live` do `ChatThread` anuncia para o turno.
 *
 * Devolve vazio enquanto a resposta chega, para o leitor de tela ouvir a
 * resposta inteira só no fim, não cada token (seção 15.8). A recusa leva a
 * nota de privacidade, e a resposta substituída começa pela nota de troca.
 */
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

/**
 * Acha a resposta, já com desfecho, que segue a pergunta enviada com
 * `clientMessageId`.
 *
 * Serve à consulta de reserva de `useAskConversation.ts` (seção 7.1). A
 * pergunta só aparece no banco depois da primeira transação da API, e a
 * resposta, depois da segunda. Devolve `null` enquanto uma delas falta.
 */
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

/**
 * Lê a carga do evento `citation`. Devolve `null` se faltar o índice, o
 * título ou o chunk. A seção do documento pode faltar.
 */
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

/**
 * Faz o parse do `data` do evento. Um valor que não é objeto vira `{}`. Um
 * texto que não é JSON lança erro, tratado em `submit`.
 */
function readPayload(data: string): Record<string, unknown> {
  const parsed: unknown = JSON.parse(data)
  if (!parsed || typeof parsed !== "object") {
    return {}
  }
  return parsed as Record<string, unknown>
}

/** Lê um campo de texto da carga, ou `null` se ele não for string. */
function textField(body: Record<string, unknown>, key: string): string | null {
  const value = body[key]
  return typeof value === "string" ? value : null
}
