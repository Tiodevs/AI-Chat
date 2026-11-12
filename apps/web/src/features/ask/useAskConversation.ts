/**
 * Controlador da conversa: liga as telas da pergunta à API e ao store.
 * Seções 7.1, 13.2 e 15.5 do SDD.
 *
 * Usado por `app/routes/home.tsx`, sem id, e por `app/routes/ask.tsx`, com
 * o id da URL. Usa o cliente tipado (`lib/api/client.ts`) para criar e ler
 * a conversa e gravar o feedback, e `lib/sse.ts` para o fluxo da resposta:
 * `EventSource` não serve, porque o envio é `POST` (seção 13.1). O estado
 * fica em `store.ts`, e o efeito de cada evento, em `model.ts`.
 *
 * `load`, `submit`, `failHttp` e `sendFeedback` ficam fora do hook: não
 * dependem do React e continuam a rodar quando a tela desmonta.
 */
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

import { seedHandoffs } from "./handoff-store.ts"
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
import type { AssistantTurn, StoredHandoff, StoredMessage } from "./types.ts"

/** Intervalo da consulta de reserva: a cada segundo (seção 7.1). */
const reserveEveryMs = 1000

/** Mensagem como o OpenAPI a descreve (`schema.ts`, seção 6.6). */
type ApiMessage = components["schemas"]["MessageResponse"]
/** Resumo de um atendimento humano da conversa (seção 29.10). */
type ApiHandoff = components["schemas"]["HandoffSummaryResponse"]

/**
 * Hook da conversa. Sem `conversationId`, serve à tela inicial.
 *
 * Lê o retrato com `useSyncExternalStore`, que assina o store externo e
 * renderiza de novo a cada `emit`. Ao montar com um id, envia a pergunta
 * que veio do início; sem ela, lê a conversa gravada se o store ainda não a
 * tem.
 *
 * Devolve o retrato e três ações:
 * - `ask(text)`: sem id, cria a conversa e navega; com id, envia.
 * - `stop()`: aborta a resposta em andamento (botão Stop).
 * - `feedback(messageId, rating)`: grava útil ou não útil, uma vez.
 */
export function useAskConversation(conversationId: string | undefined) {
  const navigate = useNavigate()
  // O terceiro argumento é o retrato do servidor, usado em SSR. Sem SSR
  // aqui, ele repete o do cliente.
  const snapshot = useSyncExternalStore(
    subscribe,
    () => selectAsk(conversationId),
    () => selectAsk(conversationId)
  )

  useEffect(() => {
    if (!conversationId) {
      return
    }
    // A pergunta do início vem primeiro: a conversa acabou de nascer e não
    // tem mensagem gravada para ler.
    const pending = takeQuestion(conversationId)
    if (pending) {
      void submit(conversationId, pending)
      return
    }
    // Uma conversa que o store já tem, lida ou com fluxo no ar, não é lida
    // de novo.
    const current = selectAsk(conversationId)
    if (current.loading || current.streaming || current.messages.length > 0) {
      return
    }
    void load(conversationId)
  }, [conversationId])

  /**
   * Primeira pergunta, feita na tela inicial (seção 15.5, Início).
   *
   * 1. Ignora o texto vazio, um pedido em andamento e a indisponibilidade.
   * 2. Cria a conversa com `POST /v1/conversations`. Sem sessão, a API
   *    define o cookie `atrium_guest` (seção 10.3).
   * 3. Guarda a pergunta no store e navega para `/ask/:id`. Quem envia é o
   *    efeito da rota nova.
   *
   * Uma falha fica no retrato da tela inicial, com o `request_id`. A
   * `HomeScreen` mostra só a mensagem, no campo do compositor.
   */
  async function start(text: string) {
    const trimmed = text.trim()
    // 1.
    if (
      !trimmed ||
      selectAsk(undefined).pending ||
      selectAsk(undefined).budgetExceeded
    ) {
      return
    }
    // 2.
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
      // 3.
      stageQuestion(created.data.id, trimmed)
      patchAsk(undefined, { pending: false, error: null })
      await navigate(`/ask/${created.data.id}`)
    } catch {
      // Falha de rede: o `fetch` rejeitou sem resposta da API.
      patchAsk(undefined, { pending: false, error: pt.couldNotContinue })
    }
  }

  /** Envia na conversa aberta ou, na tela inicial, cria a conversa antes. */
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

/**
 * Lê a conversa gravada (`GET /v1/conversations/{id}`) e troca a thread.
 *
 * Sem `force`, liga o skeleton e descarta o resultado se uma pergunta
 * começou no meio-tempo, porque o fluxo é mais novo que a leitura. Com
 * `force`, usado depois do 409, recarrega mesmo com o fluxo marcado e sem
 * trocar a thread pelo skeleton.
 */
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
    // A thread lida não traz resposta nova, então nada é anunciado. Os
    // atendimentos humanos vão para o store deles, e a thread guarda só onde
    // cada bloco aparece (seção 29.11).
    const stored = result.data.messages.map(toStored)
    const handoffs = (result.data.handoffs ?? []).map(toHandoff)
    seedHandoffs(conversationId, handoffs, stored)
    replaceMessages(conversationId, turnsFromStored(stored, handoffs), false)
  } catch {
    // Com um fluxo no ar, ele cuida da tela, e o erro da leitura é
    // descartado.
    if (!selectAsk(conversationId).streaming) {
      patchAsk(conversationId, { loading: false, error: pt.couldNotContinue })
    }
  }
}

/**
 * Envia uma pergunta e acompanha a resposta até o fim. Seção 7.1 do SDD.
 *
 * 1. Ignora o texto vazio, um fluxo já aberto e a indisponibilidade.
 * 2. Mostra a pergunta e o turno de espera na hora, antes da rede.
 * 3. Abre o `AbortController`, que o Stop e a reserva usam para fechar a
 *    conexão.
 * 4. Liga a consulta de reserva, que roda até chegar o primeiro evento.
 * 5. Faz o `POST` com `client_message_id`. Um status de erro vai para
 *    `failHttp`.
 * 6. Lê os eventos com `for await` e aplica cada um com `applyStreamEvent`,
 *    até `done` ou `error`.
 * 7. Um corpo que termina sem `done` nem `error` vira erro na tela.
 * 8. No fim, sempre: desliga a reserva e libera o controlador.
 */
async function submit(conversationId: string, text: string) {
  const trimmed = text.trim()
  const current = selectAsk(conversationId)
  // 1.
  if (!trimmed || current.streaming || current.budgetExceeded) {
    return
  }
  // 2. Um id novo por envio. O par conversa e `client_message_id` é a
  // chave de idempotência da seção 7.1: um reenvio do mesmo id recebe 409.
  // A chave do turno do assistente é local; o id da API chega no `meta`.
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
  // 3.
  const controller = openStream(conversationId)
  // Última versão do turno; cada evento parte dela.
  let draft = assistant
  // Chegou algum evento: a reserva para de consultar.
  let sawStream = false
  // Chegou `done` ou `error`: o fluxo terminou como devia.
  let finished = false
  // A reserva achou a resposta antes do fluxo e já trocou a thread.
  let settledByPoll = false
  // 4. A reserva cobre o caso da seção 7.1 em que o rewrite da Vercel não
  // entrega o primeiro evento. Ela não tem limite de tempo nem recuo; a
  // Etapa 14.2 acrescenta os dois.
  const timer = window.setInterval(() => {
    void reserve()
  }, reserveEveryMs)

  /**
   * Consulta de reserva: lê a conversa e, se a resposta desta pergunta já
   * tem desfecho, mostra a thread gravada e aborta o fluxo, que não serve
   * mais. Uma falha de rede espera a próxima volta.
   */
  async function reserve() {
    if (sawStream || settledByPoll || controller.signal.aborted) {
      return
    }
    try {
      const result = await api.GET("/v1/conversations/{conversation_id}", {
        params: { path: { conversation_id: conversationId } },
      })
      // Confere de novo depois do `await`: o fluxo pode ter começado, ou a
      // pessoa pode ter parado, enquanto o pedido ia e voltava.
      if (
        sawStream ||
        settledByPoll ||
        controller.signal.aborted ||
        !result.data
      ) {
        return
      }
      const stored = result.data.messages.map(toStored)
      const handoffs = (result.data.handoffs ?? []).map(toHandoff)
      const settled = assistantAfter(stored, clientMessageId)
      if (!settled?.outcome) {
        return
      }
      settledByPoll = true
      window.clearInterval(timer)
      // Sem eventos, a região ao vivo ainda não anunciou nada.
      replaceMessages(conversationId, turnsFromStored(stored, handoffs), true)
      if (settled.outcome === "degraded") {
        markBudgetExceeded()
      }
      // O `submit` vê `settledByPoll` e sai sem marcar erro.
      controller.abort()
    } catch {
      // A reserva tenta de novo no próximo segundo.
    }
  }

  /** Guarda a versão nova do turno e a grava no store. */
  function commit(next: AssistantTurn) {
    draft = next
    updateAssistant(conversationId, assistant.key, next)
  }

  try {
    // 5. O envio usa `fetch` com `ReadableStream` e o leitor próprio de
    // `lib/sse.ts` (seção 13.1).
    const response = await postEventStream(
      messageUrl(conversationId),
      { text: trimmed, client_message_id: clientMessageId },
      controller.signal
    )
    // Um status de erro chega antes de qualquer evento, com o envelope
    // JSON da seção 12.
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
    // 6. `readEventStream` é um gerador assíncrono: cada volta do
    // `for await` espera o próximo evento completo. Sair do laço com
    // `return` encerra o gerador, que solta o leitor do corpo.
    for await (const event of readEventStream(response.body)) {
      // Stop ou reserva: a tela já mostra o resultado, e o resto do fluxo
      // é descartado.
      if (controller.signal.aborted || settledByPoll) {
        return
      }
      sawStream = true
      try {
        commit(applyStreamEvent(draft, event))
      } catch {
        // `data` que não é JSON vira erro no turno, sem derrubar a página.
        commit({
          ...draft,
          phase: "error",
          errorMessage: pt.ask.couldNotFinish,
        })
        return
      }
      // `degraded` é o orçamento estourado ou o circuito aberto (seção 7.1).
      // Na pergunta, a API manda esse caso dentro do fluxo, não como 503.
      if (event.event === "done" && draft.outcome === "degraded") {
        markBudgetExceeded()
      }
      if (event.event === "done" || event.event === "error") {
        finished = true
        return
      }
    }
    // 7. O corpo terminou sem `done` nem `error`: a conexão caiu no meio.
    if (!finished && !settledByPoll && !controller.signal.aborted) {
      commit({
        ...draft,
        phase: "error",
        errorMessage: pt.ask.couldNotFinish,
      })
    }
  } catch {
    // O `fetch` e a leitura também rejeitam quando o sinal é abortado. O
    // Stop e a reserva já cuidaram da tela, então só uma falha de verdade,
    // como a rede, vira erro.
    if (controller.signal.aborted || settledByPoll) {
      return
    }
    commit({
      ...draft,
      phase: "error",
      errorMessage: pt.couldNotContinue,
    })
  } finally {
    // 8.
    window.clearInterval(timer)
    releaseStream(conversationId, controller)
  }
}

/**
 * Trata a resposta de erro do `POST` da pergunta, que chega antes de
 * qualquer evento.
 *
 * - 409: a pergunta já estava gravada, num reenvio do mesmo
 *   `client_message_id` (seção 7.1). Recarrega a conversa do banco.
 * - 429: limite de perguntas (seção 10.4). Tira o turno de espera e mostra
 *   o aviso em minutos, com `retry_after_seconds` ou 60 segundos.
 * - 503: marca a indisponibilidade na aba e fecha o turno como `degraded`,
 *   com o texto da API ou o de indisponibilidade.
 * - Outros, como 401, 403, 404 e 422: erro no turno, com o `request_id`.
 */
async function failHttp(
  conversationId: string,
  assistantKey: string,
  response: Response
) {
  // O corpo pode não ser JSON, como a página de erro de um proxy.
  const body: unknown = await response.json().catch(() => null)
  if (response.status === 409) {
    // A API não chama o modelo num reenvio. A thread gravada mostra o que
    // já existe.
    await load(conversationId, true)
    return
  }
  if (response.status === 429) {
    // A pergunta fica na tela, sem resposta, e o aviso aparece abaixo.
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

/**
 * Grava a avaliação de uma resposta (`POST /v1/messages/{id}/feedback`).
 * Seções 12 e 15.6 do SDD.
 *
 * 1. Ignora a resposta que não existe ou que já tem avaliação na tela.
 * 2. Mostra a escolha na hora, antes da rede (atualização otimista).
 * 3. Um 409 quer dizer que a API já tinha uma avaliação, porque ela aceita
 *    uma só: a tela trava os botões com o aviso de já avaliada. Outra
 *    falha desfaz a escolha, para a pessoa tentar de novo.
 */
async function sendFeedback(
  conversationId: string,
  messageId: string,
  rating: 1 | -1
) {
  const current = selectAsk(conversationId).messages.find((message) => {
    return message.role === "assistant" && message.id === messageId
  })
  // 1.
  if (!current || current.role !== "assistant" || current.feedback) {
    return
  }
  // 2.
  updateAssistant(conversationId, current.key, { ...current, feedback: rating })
  try {
    const result = await api.POST("/v1/messages/{message_id}/feedback", {
      params: { path: { message_id: messageId } },
      body: { rating },
    })
    if (result.response.ok) {
      return
    }
    // Relê o turno: ele pode ter mudado durante o pedido.
    const latest = selectAsk(conversationId).messages.find((message) => {
      return message.key === current.key && message.role === "assistant"
    })
    if (!latest || latest.role !== "assistant") {
      return
    }
    // 3.
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

/**
 * Turno do assistente antes do primeiro evento: fase `waiting` e sem o id
 * da API. `retryText` guarda a pergunta para o Tentar de novo.
 */
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

/** Converte a mensagem do OpenAPI, em `snake_case`, no tipo da tela. */
function toStored(message: ApiMessage): StoredMessage {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    clientMessageId: message.client_message_id,
    outcome: message.outcome,
    createdAt: message.created_at,
    handoffId: message.handoff_id ?? null,
    redaction: message.redaction ?? null,
    citations: message.citations.map((citation) => ({
      index: citation.index,
      documentTitle: citation.document_title,
      heading: citation.heading,
      chunkId: citation.chunk_id,
    })),
  }
}

/** Converte o resumo do atendimento do OpenAPI no tipo da tela. */
function toHandoff(handoff: ApiHandoff): StoredHandoff {
  return {
    id: handoff.id,
    status: handoff.status,
    closeReason: handoff.close_reason,
    requestedAt: handoff.requested_at,
  }
}

/**
 * URL absoluta do envio. O navegador chama `/backend/v1/...`, e o Vite ou a
 * Vercel encaminham para a API (seções 12 e 13.4). Numa página sem origem
 * (`"null"`), usa `http://127.0.0.1`, como `lib/api/client.ts`.
 */
function messageUrl(conversationId: string) {
  const origin =
    window.location.origin === "null"
      ? "http://127.0.0.1"
      : window.location.origin
  return `${origin}/backend/v1/conversations/${conversationId}/messages`
}

/**
 * UUID v4 gerado no navegador. `crypto.randomUUID` só existe em contexto
 * seguro: HTTPS ou `localhost`.
 */
function newId() {
  return globalThis.crypto.randomUUID()
}
