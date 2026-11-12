/**
 * O leitor de eventos enviados pelo servidor (SSE), para a resposta da
 * pergunta em fluxo (seções 7.1 e 13.1).
 *
 * O `EventSource` do navegador só faz `GET`, e a pergunta é um `POST` com
 * corpo. Por isso o pedido sai por `fetch` (`postEventStream`), e o corpo
 * da resposta, um `ReadableStream` de bytes, passa por este leitor
 * (`readEventStream`), que o corta em eventos.
 *
 * No formato SSE, um evento, ou frame, é um bloco de linhas `campo: valor`
 * que termina numa linha em branco, como `event: token` e
 * `data: {"text":"..."}`. A API usa só `event` e `data`
 * (`apps/api/app/core/sse.py`) e manda o comentário `: keepalive` a cada
 * 15 s sem token, para os proxies não fecharem a conexão.
 *
 * Quem usa: `features/ask/useAskConversation.ts`, que interpreta cada
 * evento com `features/ask/model.ts`. O arquivo fica em `lib`, onde o
 * ESLint deixa chamar `fetch` (seção 6.2).
 */

/**
 * Um evento lido do fluxo. `event` é o nome (`meta`, `token`, `replace`,
 * `citation`, `done` ou `error`, seção 7.1), ou `message` quando o bloco
 * não traz nome. `data` é o texto cru, ainda sem `JSON.parse`.
 */
export type ServerEvent = {
  event: string
  data: string
  /**
   * O campo `id:` do bloco, quando há. Os fluxos do atendimento humano o
   * mandam em cada `message`, como `{handoff_id}:{seq}` (seção 29.6).
   */
  id?: string
}

/**
 * Separa os eventos completos do texto acumulado.
 *
 * Uma leitura da rede pode terminar no meio de um evento, até no meio do
 * JSON. O pedaço depois da última linha em branco ainda não terminou: ele
 * volta como `rest`, e quem lê o junta ao começo da leitura seguinte.
 * Comentários e blocos sem `data` não viram evento.
 *
 * @param buffer O resto da leitura anterior mais o texto novo.
 * @returns Os eventos completos, na ordem, e o resto incompleto.
 */
export function takeEvents(buffer: string): {
  events: ServerEvent[]
  rest: string
} {
  // O formato aceita CRLF, LF ou CR no fim da linha: tudo vira LF antes do
  // corte. A API manda só LF.
  const normalized = buffer.replace(/\r\n/g, "\n").replace(/\r/g, "\n")
  const frames = normalized.split("\n\n")
  // O último pedaço não terminou numa linha em branco: é o resto.
  const rest = frames.pop() ?? ""
  const events: ServerEvent[] = []
  for (const frame of frames) {
    const event = parseFrame(frame)
    if (event) {
      events.push(event)
    }
  }
  return { events, rest }
}

/**
 * Lê o corpo de uma resposta SSE e entrega um evento de cada vez.
 *
 * É um gerador assíncrono: quem usa percorre com `for await`. A cada
 * leitura, decodifica os bytes, junta ao resto da anterior e entrega os
 * eventos que ficaram completos. No fim do fluxo, entrega também um último
 * evento que chegou sem a linha em branco final.
 *
 * Efeito colateral: trava o fluxo com `getReader` enquanto lê e solta a
 * trava no `finally`, que roda também quando quem usa sai do laço antes do
 * fim. Soltar a trava não cancela o pedido; quem cancela é o `AbortSignal`
 * passado a `postEventStream`.
 */
export async function* readEventStream(
  stream: ReadableStream<Uint8Array>
): AsyncGenerator<ServerEvent> {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let rest = ""
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        // Sem argumento, o decodificador entrega os bytes que guardava.
        rest += decoder.decode()
        if (rest.trim()) {
          // A linha em branco que faltou fecha o último bloco.
          const flushed = takeEvents(`${rest}\n\n`)
          for (const event of flushed.events) {
            yield event
          }
        }
        return
      }
      // `stream: true` guarda para a leitura seguinte um caractere de
      // vários bytes partido no meio, como um `á` em UTF-8.
      rest += decoder.decode(value, { stream: true })
      const taken = takeEvents(rest)
      rest = taken.rest
      for (const event of taken.events) {
        yield event
      }
    }
  } finally {
    reader.releaseLock()
  }
}

/**
 * Envia o `POST` que abre o fluxo SSE e devolve a resposta, com o corpo
 * ainda por ler.
 *
 * Usa `fetch` direto, como pede a seção 13.1: no padrão, o cliente `api`
 * esperaria o corpo inteiro para ler como JSON. `credentials: "include"`
 * manda os cookies de sessão e de convidado (seção 10.3). O `signal`
 * cancela o pedido: é o botão Parar (FR-18).
 *
 * @param url Endereço absoluto, com o prefixo `/backend`.
 * @param body O corpo, convertido em JSON: `{ text, client_message_id }`
 *   na pergunta (seção 7.1).
 */
export function postEventStream(
  url: string,
  body: unknown,
  signal: AbortSignal
): Promise<Response> {
  return fetch(url, {
    method: "POST",
    credentials: "include",
    headers: {
      "content-type": "application/json",
      accept: "text/event-stream",
    },
    body: JSON.stringify(body),
    signal,
  })
}

/**
 * Lê um bloco de linhas como um evento, pelas regras do formato SSE.
 *
 * Linhas que começam com `:` são comentários, como o `: keepalive`. Cada
 * linha se divide no primeiro `:`, e um espaço logo depois dele sai do
 * valor. Várias linhas `data` se juntam com quebra de linha. O `id` vai no
 * evento, para a retomada do atendimento (seção 29.6); `retry` fica de fora.
 *
 * @returns O evento, ou `null` quando o bloco não tem `data`, como um bloco
 *   só de comentário.
 */
function parseFrame(frame: string): ServerEvent | null {
  let event = "message"
  const data: string[] = []
  let sawData = false
  let id: string | null = null
  for (const line of frame.split("\n")) {
    if (line === "" || line.startsWith(":")) {
      continue
    }
    const colon = line.indexOf(":")
    const field = colon === -1 ? line : line.slice(0, colon)
    let value = colon === -1 ? "" : line.slice(colon + 1)
    if (value.startsWith(" ")) {
      value = value.slice(1)
    }
    if (field === "event") {
      event = value
    } else if (field === "data") {
      data.push(value)
      sawData = true
    } else if (field === "id") {
      id = value
    }
  }
  if (!sawData) {
    return null
  }
  const parsed: ServerEvent = { event, data: data.join("\n") }
  if (id !== null) {
    parsed.id = id
  }
  return parsed
}

/** Estado da conexão de um fluxo longo, para a tela mostrar Reconectando. */
export type StreamState = "open" | "reconnecting" | "closed"

/**
 * Espera entre tentativas depois de uma queda: 1, 2, 4 e até 10 segundos.
 * Depois do evento `reconnect`, o fluxo volta na hora (seção 29.6).
 */
const retryDelaysMs = [1000, 2000, 4000, 10000]

/**
 * Depois de 5 segundos sem fluxo aberto, a tela mostra "Reconectando…"
 * (seção 29.11).
 */
const reconnectingAfterMs = 5000

/**
 * Abre um fluxo `GET` longo e o mantém vivo, com retomada pelo
 * `Last-Event-ID`. Serve aos fluxos do atendimento humano (seção 29.6):
 * `GET /v1/conversations/{id}/handoff/events` e `GET /v1/attendance/events`.
 *
 * 1. Faz o `GET` com `Last-Event-ID`, quando já viu um `id:`.
 * 2. Entrega cada evento a `onEvent` e guarda o último `id`.
 * 3. No evento `reconnect`, que o servidor manda aos 10 minutos, abre de
 *    novo na hora. Numa queda, tenta de novo com espera crescente.
 * 4. Um 401, 403 ou 404, o evento `error` ou `stop()` encerram de vez.
 *
 * `onState` recebe `reconnecting` só depois de 5 segundos sem fluxo, para
 * uma reconexão rápida não piscar na tela.
 *
 * @returns `stop`, que fecha o fluxo e cancela as tentativas.
 */
export function openEventStream({
  url,
  onEvent,
  onState,
  lastEventId = null,
}: {
  url: string
  onEvent: (event: ServerEvent) => void
  onState?: (state: StreamState) => void
  lastEventId?: string | null
}): { stop: () => void } {
  let stopped = false
  let controller: AbortController | null = null
  let lastId = lastEventId
  let warnTimer: ReturnType<typeof setTimeout> | null = null

  function warnLater() {
    if (warnTimer === null) {
      warnTimer = setTimeout(() => {
        onState?.("reconnecting")
      }, reconnectingAfterMs)
    }
  }

  function clearWarning() {
    if (warnTimer !== null) {
      clearTimeout(warnTimer)
      warnTimer = null
    }
  }

  async function run() {
    let attempt = 0
    while (!stopped) {
      const current = new AbortController()
      controller = current
      let ended: "reconnect" | "drop" | "final" = "drop"
      try {
        // 1.
        const headers: Record<string, string> = {
          accept: "text/event-stream",
        }
        if (lastId) {
          headers["Last-Event-ID"] = lastId
        }
        const response = await fetch(url, {
          method: "GET",
          credentials: "include",
          headers,
          signal: current.signal,
        })
        if ([401, 403, 404].includes(response.status)) {
          ended = "final"
        } else if (response.ok && response.body) {
          clearWarning()
          onState?.("open")
          attempt = 0
          // 2.
          for await (const event of readEventStream(response.body)) {
            if (event.id) {
              lastId = event.id
            }
            onEvent(event)
            if (event.event === "reconnect") {
              ended = "reconnect"
              break
            }
            if (event.event === "error") {
              ended = "final"
              break
            }
          }
        }
      } catch {
        // Queda de rede ou `stop()`: o laço decide abaixo.
      }
      current.abort()
      if (stopped || ended === "final") {
        break
      }
      // 3.
      warnLater()
      if (ended === "drop") {
        const delay =
          retryDelaysMs[Math.min(attempt, retryDelaysMs.length - 1)] ?? 10000
        attempt += 1
        await new Promise((resolve) => setTimeout(resolve, delay))
      }
    }
    // 4.
    clearWarning()
    onState?.("closed")
  }

  void run()
  return {
    stop() {
      stopped = true
      controller?.abort()
      clearWarning()
    },
  }
}
