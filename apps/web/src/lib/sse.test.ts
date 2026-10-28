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
