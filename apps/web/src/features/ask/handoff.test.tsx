/**
 * O atendimento humano na conversa: oferta, diálogo, mensagem da equipe e a
 * retomada sem duplicar. FR-19, FR-20, FR-23 e seções 29.8, 29.9.5 e 29.11.
 *
 * Renderiza a `ConversationScreen` com um atendimento falso, sem a API: as
 * ações são `vi.fn`. O store do atendimento e o modelo da thread são
 * testados direto. Projeto `dom` do Vitest. Não usa a API nem banco.
 */
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { createMemoryRouter, RouterProvider } from "react-router"
import { describe, expect, it, vi } from "vitest"

import { AppProviders } from "@/app/providers.tsx"
import { AttendantMessage } from "@/components/patterns/attendant-message.tsx"
import { pt } from "@/i18n/pt.ts"

import {
  ConversationScreen,
  type HandoffControls,
} from "./conversation-screen.tsx"
import {
  seedHandoffs,
  selectHandoff,
  upsertHandoffMessage,
} from "./handoff-store.ts"
import { turnsFromStored } from "./model.ts"
import type { AssistantTurn, StoredMessage, Turn } from "./types.ts"

const conversationId = "00000000-0000-4000-8000-0000000000c1"
const answerId = "00000000-0000-4000-8000-0000000000a1"

/** Uma resposta concluída com o desfecho dado. */
function answer(
  outcome: string,
  feedback: AssistantTurn["feedback"] = null
): Turn[] {
  return [
    {
      key: "q",
      role: "user",
      text: "Vocês têm heliponto?",
      clientMessageId: "q",
      privacy: false,
    },
    {
      key: answerId,
      role: "assistant",
      id: answerId,
      requestId: null,
      text: "Não encontrei essa informação.",
      outgoing: null,
      citations: [],
      outcome,
      phase: "done",
      replaced: false,
      errorMessage: null,
      feedback,
      retryText: null,
    },
  ]
}

/** Um atendimento falso, aberto, sem atendimento ativo. */
function controls(partial: Partial<HandoffControls> = {}): HandoffControls {
  return {
    handoffs: {},
    activeId: null,
    availability: "open",
    blocked: false,
    reconnecting: false,
    requesting: false,
    sending: false,
    ending: false,
    error: null,
    active: null,
    request: vi.fn(async () => true),
    send: vi.fn(async () => true),
    end: vi.fn(),
    ...partial,
  }
}

/** Renderiza a tela da conversa com os turnos e o atendimento. */
function renderScreen(messages: Turn[], handoff: HandoffControls) {
  const router = createMemoryRouter(
    [
      {
        path: "/",
        element: (
          <ConversationScreen
            messages={messages}
            live=""
            loading={false}
            pending={false}
            streaming={false}
            error={null}
            requestId={null}
            rateLimit={null}
            budgetExceeded={false}
            onAsk={() => undefined}
            onStop={() => undefined}
            onFeedback={() => undefined}
            handoff={handoff}
          />
        ),
      },
    ],
    { initialEntries: ["/"] }
  )
  render(
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  )
}

describe("oferta do atendimento", () => {
  it("aparece numa abstenção com a equipe disponível e some na recusa", () => {
    // Etapa 17.6, CA-1 (FR-19).
    renderScreen(answer("abstained"), controls())
    expect(
      screen.getByRole("button", { name: pt.handoff.offerButton })
    ).toBeTruthy()
  })

  it("não aparece numa recusa médica", () => {
    renderScreen(answer("refused"), controls())
    expect(
      screen.queryByRole("button", { name: pt.handoff.offerButton })
    ).toBeNull()
  })

  it("aparece numa resposta marcada como não útil", () => {
    renderScreen(answer("answered", -1), controls())
    expect(
      screen.getByRole("button", { name: pt.handoff.offerButton })
    ).toBeTruthy()
  })

  it("troca o botão pelo telefone quando ninguém está disponível", () => {
    renderScreen(answer("abstained"), controls({ availability: "closed" }))
    expect(
      screen.queryByRole("button", { name: pt.handoff.offerButton })
    ).toBeNull()
    expect(screen.getByText(pt.handoff.closed)).toBeTruthy()
  })

  it("não mostra nada com o serviço desligado", () => {
    renderScreen(answer("abstained"), controls({ availability: "disabled" }))
    expect(screen.queryByText(pt.handoff.offerQuestion)).toBeNull()
  })
})

describe("diálogo de confirmação", () => {
  it("mostra o texto da seção 29.9.5 e só chama a API depois de Chamar a equipe", async () => {
    // Etapa 17.6, CA-2 (FR-20).
    const handoff = controls()
    renderScreen(answer("abstained"), handoff)
    const user = userEvent.setup()
    await user.click(
      screen.getByRole("button", { name: pt.handoff.offerButton })
    )
    expect(
      screen.getByRole("dialog", { name: pt.handoff.dialog.title })
    ).toBeTruthy()
    expect(screen.getByText(pt.handoff.dialog.notShared)).toBeTruthy()
    expect(screen.getByText(pt.handoff.dialog.retention)).toBeTruthy()
    expect(handoff.request).not.toHaveBeenCalled()
    await user.click(
      screen.getByRole("button", { name: pt.handoff.dialog.cancel })
    )
    expect(handoff.request).not.toHaveBeenCalled()
    await user.click(
      screen.getByRole("button", { name: pt.handoff.offerButton })
    )
    await user.click(
      screen.getByRole("button", { name: pt.handoff.dialog.confirm })
    )
    expect(handoff.request).toHaveBeenCalledWith(answerId)
  })
})

describe("mensagem da equipe", () => {
  it("tem o rótulo visível e mostra um link como texto", () => {
    // Etapa 17.6, CA-4 (seções 29.8 e 29.9.5).
    render(
      <AppProviders>
        <AttendantMessage
          text="Veja https://exemplo.invalid/pagina para mais detalhes."
          redaction={null}
        />
      </AppProviders>
    )
    expect(screen.getByText(pt.handoff.teamLabel)).toBeTruthy()
    expect(screen.getByText(/https:\/\/exemplo\.invalid\/pagina/)).toBeTruthy()
    expect(screen.queryByRole("link")).toBeNull()
  })

  it("mostra o aviso no lugar de uma mensagem removida", () => {
    render(
      <AppProviders>
        <AttendantMessage text="[mensagem removida]" redaction="health" />
      </AppProviders>
    )
    expect(screen.getByText(pt.handoff.removed)).toBeTruthy()
  })
})

describe("thread e retomada", () => {
  const stored: StoredMessage[] = [
    message("q1", "user", "2026-11-12T15:00:00Z"),
    message("a1", "assistant", "2026-11-12T15:00:01Z", null, "abstained"),
    message("h1", "user", "2026-11-12T15:01:00Z", "h"),
    message("h2", "attendant", "2026-11-12T15:02:00Z", "h"),
    message("q2", "user", "2026-11-12T15:10:00Z"),
    message("a2", "assistant", "2026-11-12T15:10:01Z", null, "answered"),
  ]

  it("tira as mensagens do atendimento da conversa com a IA e põe o bloco no lugar", () => {
    const turns = turnsFromStored(stored, [
      {
        id: "h",
        status: "closed",
        closeReason: "resolved",
        requestedAt: "2026-11-12T15:00:30Z",
      },
    ])
    expect(
      turns.map((turn) => (turn.role === "handoff" ? "bloco" : turn.key))
    ).toEqual(["q1", "a1", "bloco", "q2", "a2"])
  })

  it("não duplica a mensagem que volta pelo fluxo e troca o texto da remoção", () => {
    // Etapa 17.6, CA-3 (FR-23): a mensagem é trocada pelo id.
    seedHandoffs(
      conversationId,
      [
        {
          id: "h",
          status: "assigned",
          closeReason: null,
          requestedAt: "2026-11-12T15:00:30Z",
        },
      ],
      stored
    )
    upsertHandoffMessage(conversationId, "h", {
      id: "h1",
      seq: 1,
      role: "user",
      content: "texto",
      redaction: null,
      createdAt: "2026-11-12T15:01:00Z",
    })
    upsertHandoffMessage(conversationId, "h", {
      id: "h1",
      seq: 3,
      role: "user",
      content: "[mensagem removida]",
      redaction: "health",
      createdAt: "2026-11-12T15:01:00Z",
    })
    const messages = selectHandoff(conversationId).handoffs.h?.messages ?? []
    expect(messages.map((item) => item.id)).toEqual(["h1", "h2"])
    expect(messages[0]?.redaction).toBe("health")
  })
})

/** Uma mensagem gravada, da conversa com a IA ou do atendimento `handoffId`. */
function message(
  id: string,
  role: StoredMessage["role"],
  createdAt: string,
  handoffId: string | null = null,
  outcome: string | null = null
): StoredMessage {
  return {
    id,
    role,
    content: id,
    clientMessageId: role === "user" ? id : null,
    citations: [],
    outcome,
    createdAt,
    handoffId,
    redaction: null,
  }
}
