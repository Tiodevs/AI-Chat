import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { createMemoryRouter, RouterProvider } from "react-router"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { AppProviders } from "@/app/providers.tsx"
import { ChatThread } from "@/components/patterns/chat-thread.tsx"
import { pt } from "@/i18n/pt.ts"

import type { Turn } from "./types.ts"
import { useAskConversation } from "./useAskConversation.ts"

const conversationId = "00000000-0000-4000-8000-0000000000a1"

function Harness() {
  const ask = useAskConversation(conversationId)
  return (
    <div>
      <button
        type="button"
        onClick={() => ask.ask("Qual é o horário de visita?")}
      >
        enviar
      </button>
      <button type="button" onClick={() => ask.stop()}>
        parar
      </button>
      <p role="status">{ask.live}</p>
      {ask.messages.map((message) => (
        <p key={message.key}>
          {message.role === "user"
            ? message.text
            : `${message.phase}:${message.text}`}
        </p>
      ))}
    </div>
  )
}

function renderHarness() {
  const router = createMemoryRouter([{ path: "/", element: <Harness /> }], {
    initialEntries: ["/"],
  })
  render(
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  )
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  })
}

function emptyConversation() {
  return json({
    id: conversationId,
    created_at: "2026-10-27T12:00:00Z",
    messages: [],
  })
}

describe("pedido da conversa", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => emptyConversation())
    )
  })

  it("replace troca o rascunho e o anúncio espera o done", async () => {
    const user = userEvent.setup()
    const encoder = new TextEncoder()
    const frames = [
      'event: meta\ndata: {"message_id":"asst-1","request_id":"req-1"}\n\n',
      'event: token\ndata: {"text":"rascunho ruim"}\n\n',
      'event: replace\ndata: {"text":"texto seguro","reason":"grounding_failed"}\n\n',
      'event: done\ndata: {"outcome":"grounding_failed"}\n\n',
    ]
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const method =
          input instanceof Request ? input.method : (init?.method ?? "GET")
        if (method === "POST") {
          return new Response(
            new ReadableStream({
              start(controller) {
                for (const frame of frames) {
                  controller.enqueue(encoder.encode(frame))
                }
                controller.close()
              },
            }),
            { status: 200, headers: { "content-type": "text/event-stream" } }
          )
        }
        return emptyConversation()
      })
    )
    renderHarness()
    await user.click(await screen.findByRole("button", { name: "enviar" }))
    expect(await screen.findByText("done:texto seguro")).toBeInTheDocument()
    expect(screen.queryByText("done:rascunho ruim")).not.toBeInTheDocument()
    expect(screen.getByRole("status")).toHaveTextContent(
      `${pt.ask.replacedNote} texto seguro`
    )
    expect(screen.getByRole("status")).not.toHaveTextContent("rascunho ruim")
  })

  it("Stop aborta o pedido e mostra a interrupção", async () => {
    const user = userEvent.setup()
    let signal: AbortSignal | undefined
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const method =
          input instanceof Request ? input.method : (init?.method ?? "GET")
        if (method === "POST") {
          signal = init?.signal ?? undefined
          return new Response(new ReadableStream(), {
            status: 200,
            headers: { "content-type": "text/event-stream" },
          })
        }
        return emptyConversation()
      })
    )
    renderHarness()
    await user.click(await screen.findByRole("button", { name: "enviar" }))
    expect(
      await screen.findByText("Qual é o horário de visita?")
    ).toBeInTheDocument()
    await waitFor(() => {
      expect(signal).toBeDefined()
    })
    await user.click(screen.getByRole("button", { name: "parar" }))
    expect(signal?.aborted).toBe(true)
    expect(await screen.findByText(`cancelled:${""}`)).toBeInTheDocument()
    expect(screen.getByRole("status")).toHaveTextContent(pt.ask.interrupted)
  })

  it("consulta a conversa a cada segundo se o primeiro evento não chega", async () => {
    vi.useFakeTimers()
    try {
      let clientMessageId = ""
      vi.stubGlobal(
        "fetch",
        vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
          const method =
            input instanceof Request ? input.method : (init?.method ?? "GET")
          const url = input instanceof Request ? input.url : String(input)
          if (method === "POST" && url.includes("/messages")) {
            clientMessageId = (
              JSON.parse(String(init?.body)) as { client_message_id: string }
            ).client_message_id
            return new Response(new ReadableStream(), {
              status: 200,
              headers: { "content-type": "text/event-stream" },
            })
          }
          if (!clientMessageId) {
            return emptyConversation()
          }
          return json({
            id: conversationId,
            created_at: "2026-10-27T12:00:00Z",
            messages: [
              {
                id: "user-1",
                role: "user",
                content: "Qual é o horário de visita?",
                client_message_id: clientMessageId,
                citations: [],
                outcome: null,
                created_at: "2026-10-27T12:00:01Z",
              },
              {
                id: "assistant-1",
                role: "assistant",
                content: "O horário é 11:00.",
                client_message_id: null,
                citations: [],
                outcome: "answered",
                created_at: "2026-10-27T12:00:02Z",
              },
            ],
          })
        })
      )
      renderHarness()
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0)
      })
      fireEvent.click(screen.getByRole("button", { name: "enviar" }))
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1000)
      })
      expect(screen.getByText("done:O horário é 11:00.")).toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })
})

describe("anúncio da thread", () => {
  it("a região ao vivo recebe a resposta inteira só no done", () => {
    const partial: Turn[] = [
      {
        key: "user",
        role: "user",
        text: "Qual é o horário de visita?",
        clientMessageId: "user",
        privacy: false,
      },
      {
        key: "assistant",
        role: "assistant",
        id: "assistant",
        requestId: "req",
        text: "pedaço",
        outgoing: null,
        citations: [],
        outcome: null,
        phase: "streaming",
        replaced: false,
        errorMessage: null,
        feedback: null,
        retryText: "Qual é o horário de visita?",
      },
    ]
    const { rerender } = render(
      <AppProviders>
        <ChatThread
          messages={partial}
          live=""
          onFeedback={() => undefined}
          onRetry={() => undefined}
        />
      </AppProviders>
    )
    expect(screen.getByRole("status")).toHaveTextContent("")
    expect(screen.getByText("pedaço")).toBeInTheDocument()
    const done: Turn[] = [
      partial[0]!,
      {
        ...(partial[1] as Extract<Turn, { role: "assistant" }>),
        text: "O horário é 11:00.",
        phase: "done",
        outcome: "answered",
      },
    ]
    rerender(
      <AppProviders>
        <ChatThread
          messages={done}
          live="O horário é 11:00."
          onFeedback={() => undefined}
          onRetry={() => undefined}
        />
      </AppProviders>
    )
    expect(screen.getByRole("status")).toHaveTextContent("O horário é 11:00.")
  })
})
