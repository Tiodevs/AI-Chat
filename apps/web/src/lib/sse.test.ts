/**
 * O leitor SSE de `src/lib/sse.ts` junta eventos partidos entre leituras e
 * ignora comentários. Seções 7.1, 13.1 e 21.1 do SDD.
 *
 * `takeEvents` recebe o texto acumulado e devolve os eventos completos e o
 * resto; `readEventStream` lê um `ReadableStream` montado no teste, com o
 * corte no meio do JSON. Roda no projeto `dom` do Vitest, embora não use a
 * tela. Não usa `fetch`, a API nem banco.
 */
import { describe, expect, it, vi } from "vitest"

import {
  openEventStream,
  readEventStream,
  takeEvents,
  type ServerEvent,
} from "./sse.ts"

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

  it("lê o campo id de cada evento", () => {
    const taken = takeEvents('id: h:3\nevent: message\ndata: {"seq":3}\n\n')
    expect(taken.events).toEqual([
      { event: "message", data: '{"seq":3}', id: "h:3" },
    ])
  })

  it("reabre o fluxo depois do reconnect com o Last-Event-ID, sem repetir", async () => {
    // Etapa 17.6, CA-3, e FR-23: a segunda conexão leva o último `id:`.
    const bodies = [
      'id: h:1\nevent: message\ndata: {"seq":1}\n\nevent: reconnect\ndata: {}\n\n',
      'id: h:2\nevent: message\ndata: {"seq":2}\n\nevent: error\ndata: {"code":"x"}\n\n',
    ]
    const seen: (string | null)[] = []
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, init: RequestInit) => {
        const headers = new Headers(init.headers)
        seen.push(headers.get("Last-Event-ID"))
        return new Response(bodies.shift() ?? "", {
          status: 200,
          headers: { "content-type": "text/event-stream" },
        })
      })
    )
    const events: ServerEvent[] = []
    await new Promise<void>((resolve) => {
      openEventStream({
        url: "http://127.0.0.1/backend/v1/attendance/events",
        onEvent: (event) => {
          events.push(event)
        },
        onState: (state) => {
          if (state === "closed") {
            resolve()
          }
        },
      })
    })
    expect(seen).toEqual([null, "h:1"])
    expect(
      events
        .filter((event) => event.event === "message")
        .map((event) => event.id)
    ).toEqual(["h:1", "h:2"])
  })
})
