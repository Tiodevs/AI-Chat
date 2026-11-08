/**
 * Tipos da conversa na tela: o vocabulário comum do modelo, do store, do
 * hook e das views da pergunta. Seções 7.1 e 15.5 do SDD.
 *
 * Usado por todos os arquivos de `features/ask` e por `ChatThread`,
 * `AssistantMessage` e `SourceList`, em `components/patterns`. Não importa
 * nada: `toStored`, em `useAskConversation.ts`, converte a mensagem do
 * OpenAPI (`MessageResponse`) nestes tipos.
 */

/**
 * Conteúdo que a API grava no lugar de uma pergunta de orientação médica
 * (seção 7.1, passo 8). Igual a `HEALTH_MESSAGE_MARKER`, de
 * `apps/api/app/domain/questions.py`. A tela troca o marcador pela nota de
 * privacidade (seção 15.5, Recusa médica).
 */
export const HEALTH_MARKER = "[health-related message not stored]"

/** Fonte citada na resposta, vinda do evento `citation` ou do banco. */
export type CitationView = {
  /** Número do marcador `[n]` no texto da resposta. */
  index: number
  documentTitle: string
  /** Título da seção do documento, ou `null` quando o trecho não tem. */
  heading: string | null
  chunkId: string
}

/**
 * Avaliação da resposta. `1` é útil e `-1` é não útil, como no corpo de
 * `POST /v1/messages/{id}/feedback`. `"locked"` marca a resposta que a API
 * já tinha avaliada (409). `null` é sem avaliação.
 */
export type FeedbackState = 1 | -1 | "locked" | null

/**
 * Fase do turno do assistente. `AssistantMessage` escolhe o estado da
 * seção 15.5 por ela:
 * - `waiting`: pedido enviado, nenhum token ainda. Skeleton e caret.
 * - `streaming`: os tokens chegam e o texto cresce, com o caret.
 * - `done`: chegou o `done`. Texto, fontes e as ações de feedback.
 * - `cancelled`: a pessoa parou, ou o banco gravou `cancelled`.
 * - `error`: o pedido ou o fluxo falhou. Mensagem e Tentar de novo.
 *
 * Em `waiting` e `streaming`, o compositor troca Enviar por Stop.
 */
export type AssistantPhase =
  "waiting" | "streaming" | "done" | "cancelled" | "error"

/** Pergunta do visitante na thread. */
export type UserTurn = {
  /**
   * Chave do item na lista do React. No envio, é o `clientMessageId`; numa
   * mensagem lida do banco, o `id` dela.
   */
  key: string
  role: "user"
  text: string
  /**
   * Id gerado no navegador e enviado como `client_message_id`. O par
   * conversa e id é único na API, que responde 409 a um reenvio (seção
   * 7.1).
   */
  clientMessageId: string
  /**
   * Pergunta de orientação médica: a tela mostra a nota de privacidade no
   * lugar do texto (seção 15.5, Recusa médica).
   */
  privacy: boolean
}

/** Resposta do assistente na thread, montada evento a evento. */
export type AssistantTurn = {
  /**
   * Chave local, criada antes de a API responder. Não muda quando o `meta`
   * chega, então o React mantém o mesmo elemento durante o fluxo.
   */
  key: string
  role: "assistant"
  /** Id da mensagem na API, que chega no `meta`. `null` antes dele. */
  id: string | null
  /** `request_id` do `meta` ou do envelope de erro, para o `RequestIdCopy`. */
  requestId: string | null
  text: string
  /**
   * Rascunho que saiu quando chegou o `replace`. Serve só à animação de
   * saída da M9 (seção 16.3) e fica fora do leitor de tela.
   */
  outgoing: string | null
  citations: CitationView[]
  /** Desfecho da seção 7.1, do evento `done` ou do banco. */
  outcome: string | null
  phase: AssistantPhase
  /** A fundamentação falhou, e a resposta segura tomou o lugar do rascunho. */
  replaced: boolean
  /** Texto mostrado na fase `error`. */
  errorMessage: string | null
  feedback: FeedbackState
  /**
   * Pergunta que o botão Tentar de novo envia outra vez. `null` quando não
   * há o que repetir: uma resposta gravada que não foi interrompida, ou uma
   * pergunta médica, que o banco guarda só com o marcador.
   */
  retryText: string | null
}

/** Um item da thread: pergunta ou resposta. */
export type Turn = UserTurn | AssistantTurn

/**
 * Retrato de uma conversa no store (`store.ts`). A tela lê só isto, por
 * `useSyncExternalStore`, e cada escrita troca o objeto inteiro.
 */
export type AskSnapshot = {
  messages: Turn[]
  /**
   * Texto da região `aria-live` do `ChatThread`. Recebe a resposta inteira
   * no fim, não cada token (seção 15.8).
   */
  live: string
  /** Lendo a conversa gravada (`GET /v1/conversations/{id}`). */
  loading: boolean
  /** Criando a conversa a partir do início (`POST /v1/conversations`). */
  pending: boolean
  /** Há uma resposta em andamento. */
  streaming: boolean
  /** Erro fora de um turno, como a conversa que não carregou. */
  error: string | null
  requestId: string | null
  /** Aviso do limite de perguntas, já em minutos (seção 10.4). */
  rateLimit: string | null
  /**
   * Uma resposta `degraded` ou um 503 marcaram a indisponibilidade nesta
   * aba. O compositor e as sugestões ficam desabilitados, com o texto de
   * indisponibilidade (seção 15.5, Início). Veja `markBudgetExceeded`.
   */
  budgetExceeded: boolean
}

/**
 * Mensagem como a API grava, com os nomes do frontend. Vem de
 * `GET /v1/conversations/{id}`, convertida por `toStored`.
 */
export type StoredMessage = {
  id: string
  role: "user" | "assistant"
  content: string
  /** Só a pergunta do visitante tem. A resposta vem com `null`. */
  clientMessageId: string | null
  citations: CitationView[]
  /** Desfecho da resposta. A pergunta do visitante vem com `null`. */
  outcome: string | null
}
