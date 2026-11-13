/**
 * O selo WhatsApp na fila e o status de entrega no console. Seções 30.5 e
 * 30.11 do SDD.
 */
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { HandoffThread, deliveryText } from "./handoff-thread.tsx"
import { QueueList } from "./queue-list.tsx"
import { MotionProvider } from "@/motion/MotionProvider.tsx"

describe("canal WhatsApp no console", () => {
  it("mostra o selo WhatsApp e nunca um número", () => {
    render(
      <MotionProvider>
        <QueueList
          items={[
            {
              handoffId: "w1",
              label: "Visitante 3f9a1c22",
              queuedAt: "2026-11-12T15:00:00Z",
              trigger: "abstained",
              returned: false,
              visitorPresent: true,
              channel: "whatsapp",
            },
          ]}
          now={new Date("2026-11-12T15:02:00Z")}
          canTake
          onTake={() => undefined}
        />
      </MotionProvider>
    )
    expect(screen.getByText("WhatsApp")).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/\d{8,}/)
  })

  it("mostra o status de entrega e o motivo da falha", () => {
    render(
      <HandoffThread
        conversation={[]}
        messages={[
          {
            id: "m1",
            role: "attendant",
            content: "Olá",
            redaction: null,
            delivery: "read",
          },
          {
            id: "m2",
            role: "attendant",
            content: "Mais algo?",
            redaction: null,
            delivery: "failed",
            deliveryError: "A janela de 24 horas do WhatsApp terminou.",
          },
        ]}
        readOnly
      />
    )
    expect(screen.getByText("Lida")).toBeInTheDocument()
    expect(
      screen.getByText(
        "Não entregue: A janela de 24 horas do WhatsApp terminou."
      )
    ).toBeInTheDocument()
    expect(deliveryText("sent", null)).toBe("Enviada")
  })
})
