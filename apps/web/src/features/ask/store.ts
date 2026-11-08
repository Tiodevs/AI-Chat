/**
 * Store das conversas, fora do React. Seções 7.1 e 13.2 do SDD.
 *
 * Guarda o retrato (`AskSnapshot`) de cada conversa e o da tela inicial, o
 * `AbortController` de cada fluxo e a pergunta que atravessa a navegação de
 * `/` para `/ask/:id`. As views leem com `useSyncExternalStore`, em
 * `useAskConversation.ts`: `subscribe` registra quem quer saber das
 * mudanças, e `selectAsk` devolve o retrato atual. Cada escrita cria um
 * retrato novo e chama `emit`.
 *
 * Como o estado vive no módulo, e não num componente, ele sobrevive à troca
 * de rota: um fluxo SSE continua a escrever aqui quando a tela da conversa
 * desmonta, e a conversa já lida não é pedida de novo ao voltar. O mesmo
 * lugar deixa `stop()` alcançar o `AbortController` de qualquer render, e
 * `resetAskState` limpar tudo na saída da conta.
 *
 * A seção 13.2 põe o modelo em `src/lib/api` e no cache do TanStack Query.
 * A conversa guarda os dados do servidor neste store próprio.
 *
 * Usado por `useAskConversation.ts`, por `useSignOut` (`features/auth`) e
 * por `src/test/setup.ts`, que limpa o store depois de cada teste. Usa
 * `syncPrivacy` e `announcementFor`, de `model.ts`, e o `sessionStorage`.
 */
import { announcementFor, syncPrivacy } from "./model.ts"
import type { AskSnapshot, AssistantTurn, Turn } from "./types.ts"

/**
 * Chave do `sessionStorage` que lembra a indisponibilidade na aba. Ela
 * sobrevive a uma recarga e some ao fechar a aba ou sair da conta.
 */
const BUDGET_KEY = "atrium.budget-exceeded"

/** Item do mapa de conversas. `write` troca o `snapshot` a cada mudança. */
type Entry = {
  snapshot: AskSnapshot
}

/** Funções que o `useSyncExternalStore` registrou por `subscribe`. */
const listeners = new Set<() => void>()
/** Retrato de cada conversa aberta nesta aba, pelo id. */
const entries = new Map<string, Entry>()
/** Fluxo em andamento de cada conversa. No máximo um por conversa. */
const controllers = new Map<string, AbortController>()
/**
 * Pergunta digitada no início, à espera da rota `/ask/:id`. `start` grava
 * antes de navegar, e o efeito da rota nova a consome com `takeQuestion`.
 */
let pendingQuestion: { id: string; text: string } | null = null
/** Retrato da tela inicial, que ainda não tem conversa. */
let home = blank()
/**
 * Retrato de uma conversa que o store ainda não conhece. É sempre o mesmo
 * objeto até mudar: o `useSyncExternalStore` compara os retratos por
 * referência, e um objeto novo a cada leitura faria a tela renderizar sem
 * parar.
 */
let empty = blank()

/**
 * Registra um ouvinte e devolve a função que o remove. É o primeiro
 * argumento do `useSyncExternalStore`: o React chama o ouvinte a cada
 * `emit` e relê o retrato com `selectAsk`.
 */
export function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/**
 * Retrato atual da conversa, ou o da tela inicial quando não há id. Devolve
 * a mesma referência enquanto nada mudou (veja `empty`).
 */
export function selectAsk(conversationId: string | undefined): AskSnapshot {
  if (!conversationId) {
    return home
  }
  return entries.get(conversationId)?.snapshot ?? empty
}

/** Guarda a pergunta do início para a conversa que acabou de nascer. */
export function stageQuestion(conversationId: string, text: string) {
  pendingQuestion = { id: conversationId, text }
}

/**
 * Entrega a pergunta guardada para esta conversa e a apaga. Ler uma vez só
 * impede que a pergunta seja enviada de novo quando a rota monta outra vez.
 */
export function takeQuestion(conversationId: string): string | null {
  if (pendingQuestion?.id !== conversationId) {
    return null
  }
  const text = pendingQuestion.text
  pendingQuestion = null
  return text
}

/**
 * Mescla campos no retrato e avisa os ouvintes. Sem id, muda o retrato da
 * tela inicial.
 */
export function patchAsk(
  conversationId: string | undefined,
  partial: Partial<AskSnapshot>
) {
  write(conversationId, partial)
  emit()
}

/**
 * Acrescenta a pergunta e o turno de espera do assistente. Limpa o erro e o
 * aviso de limite anteriores e liga `streaming`, que troca Enviar por Stop.
 */
export function appendTurns(conversationId: string, turns: Turn[]) {
  const current = ensure(conversationId).snapshot
  write(conversationId, {
    messages: syncPrivacy([...current.messages, ...turns]),
    loading: false,
    error: null,
    rateLimit: null,
    streaming: true,
  })
  emit()
}

/**
 * Troca o turno do assistente pela versão nova e recalcula o anúncio.
 *
 * Enquanto `announcementFor` devolve vazio, `live` mantém o texto anterior.
 * Por isso um anúncio igual ao último não muda a região e não é lido de
 * novo. A Etapa 14.3 corrige isso para o erro repetido.
 */
export function updateAssistant(
  conversationId: string,
  assistantKey: string,
  turn: AssistantTurn
) {
  const current = ensure(conversationId).snapshot
  const messages = syncPrivacy(
    current.messages.map((message) => {
      return message.key === assistantKey ? turn : message
    })
  )
  const announced = announcementFor(turn)
  write(conversationId, {
    messages,
    live: announced || current.live,
    // O fim do turno desliga `streaming` e devolve o botão Enviar.
    streaming: turn.phase === "waiting" || turn.phase === "streaming",
  })
  emit()
}

/**
 * Troca a thread inteira pelos turnos dados e encerra a carga e o fluxo.
 *
 * Com `announce`, anuncia a última resposta: é o caso da consulta de
 * reserva, que entrega a resposta sem eventos. A leitura da conversa
 * (`load`) passa `false`, porque não traz resposta nova.
 */
export function replaceMessages(
  conversationId: string,
  messages: Turn[],
  announce: boolean
) {
  const synced = syncPrivacy(messages)
  const latest = [...synced]
    .reverse()
    .find((message) => message.role === "assistant")
  write(conversationId, {
    messages: synced,
    loading: false,
    streaming: false,
    live:
      announce && latest && latest.role === "assistant"
        ? announcementFor(latest)
        : ensure(conversationId).snapshot.live,
  })
  emit()
}

/**
 * Marca a indisponibilidade em todos os retratos e no `sessionStorage`.
 *
 * `useAskConversation.ts` chama quando uma resposta tem desfecho `degraded`
 * (orçamento estourado ou circuito aberto, seção 7.1) e quando a API
 * responde 503. A marca vale para a aba toda até `resetAskState`: o
 * compositor e as sugestões ficam desabilitados (seção 15.5, Início).
 */
export function markBudgetExceeded() {
  try {
    sessionStorage.setItem(BUDGET_KEY, "1")
  } catch {
    // O estado em memória continua valendo quando o armazenamento está bloqueado.
  }
  const withBudget = (snapshot: AskSnapshot): AskSnapshot => ({
    ...snapshot,
    budgetExceeded: true,
  })
  // `empty` leva a marca às conversas que `ensure` ainda vai criar.
  empty = withBudget(empty)
  home = withBudget(home)
  for (const entry of entries.values()) {
    entry.snapshot = withBudget(entry.snapshot)
  }
  emit()
}

/**
 * Cria o `AbortController` do fluxo novo da conversa e aborta o anterior,
 * se houver. O `signal` vai para o `fetch` em `postEventStream`: abortar
 * fecha a conexão e faz o `fetch` ou a leitura do corpo rejeitarem.
 */
export function openStream(conversationId: string) {
  controllers.get(conversationId)?.abort()
  const controller = new AbortController()
  controllers.set(conversationId, controller)
  return controller
}

/**
 * Libera o controlador no fim de `submit` e desliga `streaming`.
 *
 * Só age se o controlador ainda é o atual. Assim, depois de um Stop seguido
 * de outra pergunta, o `finally` do fluxo antigo não desliga o novo.
 */
export function releaseStream(
  conversationId: string,
  controller: AbortController
) {
  if (controllers.get(conversationId) !== controller) {
    return
  }
  controllers.delete(conversationId)
  const current = entries.get(conversationId)
  if (!current?.snapshot.streaming) {
    return
  }
  write(conversationId, { streaming: false })
  emit()
}

/**
 * Botão Stop: aborta o fluxo e marca a resposta em andamento como
 * Interrompida (seção 15.5).
 *
 * A API percebe a conexão fechada. No código atual, ela cancela a geração e
 * grava `cancelled`, como diz a seção 6.4; a seção 7.1 diz que o pedido
 * segue até o fim. A Etapa 13.4 decide entre as duas regras.
 */
export function stopStream(conversationId: string) {
  controllers.get(conversationId)?.abort()
  controllers.delete(conversationId)
  const current = entries.get(conversationId)
  if (!current) {
    return
  }
  // Cópia rasa: o array do retrato antigo não pode mudar, porque o React
  // compara os retratos por referência.
  const messages = current.snapshot.messages.map((message) => message)
  // Só a última resposta em andamento é interrompida.
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    if (
      message?.role === "assistant" &&
      (message.phase === "waiting" || message.phase === "streaming")
    ) {
      messages[index] = {
        ...message,
        phase: "cancelled",
        text: "",
        outgoing: null,
      }
      break
    }
  }
  write(conversationId, {
    messages,
    streaming: false,
    // Um turno fictício, só para `announcementFor` devolver o texto de
    // Interrompida.
    live: announcementFor({
      key: "cancelled",
      role: "assistant",
      id: null,
      requestId: null,
      text: "",
      outgoing: null,
      citations: [],
      outcome: "cancelled",
      phase: "cancelled",
      replaced: false,
      errorMessage: null,
      feedback: null,
      retryText: null,
    }),
  })
  emit()
}

/**
 * Remove o turno de espera do assistente. Serve ao 429: a API recusa a
 * pergunta antes de gravá-la, e a tela mostra só o aviso de limite.
 */
export function dropAssistant(conversationId: string, assistantKey: string) {
  const current = ensure(conversationId).snapshot
  write(conversationId, {
    messages: current.messages.filter(
      (message) => message.key !== assistantKey
    ),
    streaming: false,
  })
  emit()
}

/**
 * Volta o store ao estado inicial: aborta os fluxos, esquece as conversas,
 * a pergunta pendente e a marca de indisponibilidade, e avisa os ouvintes.
 * Chamado na saída da conta (`useSignOut`) e depois de cada teste.
 */
export function resetAskState() {
  for (const controller of controllers.values()) {
    controller.abort()
  }
  controllers.clear()
  entries.clear()
  pendingQuestion = null
  try {
    sessionStorage.removeItem(BUDGET_KEY)
  } catch {
    // O navegador pode bloquear o armazenamento. O estado em memória segue limpo.
  }
  home = blank()
  empty = blank()
  emit()
}

/**
 * Devolve o item da conversa e o cria vazio se faltar. O item novo herda a
 * marca de indisponibilidade que `empty` carrega.
 */
function ensure(conversationId: string) {
  const existing = entries.get(conversationId)
  if (existing) {
    return existing
  }
  const created = {
    snapshot: { ...blank(), budgetExceeded: empty.budgetExceeded },
  }
  entries.set(conversationId, created)
  return created
}

/**
 * Grava os campos num retrato novo, sem avisar ninguém: quem chama decide
 * quando chamar `emit`. Sem id, escreve no retrato da tela inicial.
 */
function write(
  conversationId: string | undefined,
  partial: Partial<AskSnapshot>
) {
  if (!conversationId) {
    home = { ...home, ...partial }
    return
  }
  const entry = ensure(conversationId)
  entry.snapshot = { ...entry.snapshot, ...partial }
}

/** Avisa os ouvintes de que algum retrato mudou. */
function emit() {
  for (const listener of listeners) {
    listener()
  }
}

export type { AskSnapshot }

/** Retrato vazio, com a marca de indisponibilidade lida da aba. */
function blank(): AskSnapshot {
  return {
    messages: [],
    live: "",
    loading: false,
    pending: false,
    streaming: false,
    error: null,
    requestId: null,
    rateLimit: null,
    budgetExceeded: readBudget(),
  }
}

/**
 * Lê a marca da aba. Com o armazenamento bloqueado, o acesso lança erro, e
 * vale `false`.
 */
function readBudget() {
  try {
    return sessionStorage.getItem(BUDGET_KEY) === "1"
  } catch {
    return false
  }
}
