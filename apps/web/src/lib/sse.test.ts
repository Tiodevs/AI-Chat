/**
 * O leitor SSE de `src/lib/sse.ts` junta eventos partidos entre leituras e
 * ignora comentários. Seções 7.1, 13.1 e 21.1 do SDD.
 *
 * `takeEvents` recebe o texto acumulado e devolve os eventos completos e o
 * resto; `readEventStream` lê um `ReadableStream` montado no teste, com o
 * corte no meio do JSON. Roda no projeto `dom` do Vitest, embora não use a
 * tela. Não usa `fetch`, a API nem banco.
 */
import { describe, expect, it } from "vitest"

import { readEventStream, takeEvents } from "./sse.ts"

describe("leitor SSE", () => {
  it("junta um evento partido entre leituras", async () => {
    const first = 'event: token\ndata: {"text":"horá'
    const second = 'rio"}\n\n'
    const partial = takeEvents(first)
    expect(partial.events).toEqual([])
    expect(partial.rest).toBe(first)

    const joined = takeEvents(partial.rest + second)
    expect(joined.events).toEqual([
      { event: "token", data: '{"text":"horário"}' },
    ])
    expect(joined.rest).toBe("")
  })

  it("entrega eventos completos que chegam no mesmo bloco", () => {
    const buffer = [
      'event: meta\ndata: {"message_id":"m","request_id":"r"}\n\n',
      ": keepalive\n\n",
      'event: token\ndata: {"text":"11:00"}\n\n',
    ].join("")
    const taken = takeEvents(buffer)
    expect(taken.events.map((event) => event.event)).toEqual(["meta", "token"])
    expect(taken.events[1]?.data).toBe('{"text":"11:00"}')
  })

  it("lê o fluxo quando o corte cai no meio do JSON", async () => {
    const encoder = new TextEncoder()
    // O `done` chega sem a linha em branco final: o leitor o entrega quando o
    // fluxo fecha.
    const chunks = [
      'event: token\ndata: {"text":"vis',
      'ita"}\n\nevent: done\ndata: {"outcome":"answered"}',
    ]
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) {
          controller.enqueue(encoder.encode(chunk))
        }
        controller.close()
      },
    })
    const events = []
    for await (const event of readEventStream(stream)) {
      events.push(event)
    }
    expect(events).toEqual([
      { event: "token", data: '{"text":"visita"}' },
      { event: "done", data: '{"outcome":"answered"}' },
    ])
  })
})
