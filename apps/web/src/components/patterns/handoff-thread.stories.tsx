import type { Meta, StoryObj } from "@storybook/react-vite"

import {
  HandoffThread,
  type ThreadLine,
  type ThreadMessage,
} from "@/components/patterns/handoff-thread.tsx"

const conversation: ThreadLine[] = [
  {
    id: "q1",
    role: "user",
    content: "Vocês têm heliponto?",
    citations: [],
    outcome: null,
  },
  {
    id: "r1",
    role: "assistant",
    content: "Não encontrei essa informação nas informações publicadas.",
    citations: [],
    outcome: "abstained",
  },
  {
    id: "q2",
    role: "user",
    content: "[health-related message not stored]",
    citations: [],
    outcome: null,
  },
  {
    id: "r2",
    role: "assistant",
    content: "A visita na enfermaria vai das 11:00 às 20:00 [1].",
    citations: [{ index: 1, documentTitle: "Visitas", heading: "Horários" }],
    outcome: "answered",
  },
]

const messages: ThreadMessage[] = [
  {
    id: "m1",
    role: "user",
    content: "Preciso de ajuda com a visita.",
    redaction: null,
  },
  {
    id: "m2",
    role: "attendant",
    content: "Claro. Veja https://exemplo.invalid: o link fica como texto.",
    redaction: null,
  },
  {
    id: "m3",
    role: "user",
    content: "[mensagem removida]",
    redaction: "health",
  },
]

const meta = {
  title: "Patterns/HandoffThread",
  component: HandoffThread,
  args: { conversation, messages, onRedact: () => undefined },
} satisfies Meta<typeof HandoffThread>

export default meta

type Story = StoryObj<typeof meta>

export const ComAcoes: Story = {}

export const SoLeitura: Story = { args: { readOnly: true } }

export const SemMensagens: Story = { args: { messages: [] } }

// No WhatsApp, a mensagem da equipe mostra o status de entrega (seção 30.5).
export const WhatsAppEntrega: Story = {
  args: {
    messages: [
      { ...messages[0], id: "w1" },
      { ...messages[1], id: "w2", delivery: "read" },
      {
        id: "w3",
        role: "attendant",
        content: "Posso ajudar em algo mais?",
        redaction: null,
        delivery: "failed",
        deliveryError: "A janela de 24 horas do WhatsApp terminou.",
      },
    ],
  },
}
