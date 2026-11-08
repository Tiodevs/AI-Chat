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
 * valor. Várias linhas `data` se juntam com quebra de linha. Campos que a
 * API não usa, como `id` e `retry`, ficam de fora.
 *
 * @returns O evento, ou `null` quando o bloco não tem `data`, como um bloco
 *   só de comentário.
 */
function parseFrame(frame: string): ServerEvent | null {
  let event = "message"
  const data: string[] = []
  let sawData = false
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
    }
  }
  if (!sawData) {
    return null
  }
  return { event, data: data.join("\n") }
}
