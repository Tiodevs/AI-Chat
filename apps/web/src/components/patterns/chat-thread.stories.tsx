import type { Meta, StoryObj } from "@storybook/react-vite"

import { ChatThread } from "@/components/patterns/chat-thread.tsx"
import type { Turn } from "@/features/ask/types.ts"
import { pt } from "@/i18n/pt.ts"

const messages: Turn[] = [
  {
    key: "user-1",
    role: "user",
    text: pt.ask.suggestions[0].question,
    clientMessageId: "user-1",
    privacy: false,
  },
  {
    key: "assistant-1",
    role: "assistant",
    id: "assistant-1",
    requestId: "req-1",
    text: "O horário de visita é das 11:00 às 20:00 [1].",
    outgoing: null,
    citations: [
      {
        index: 1,
        documentTitle: "Visitas",
        heading: "Horário",
        chunkId: "00000000-0000-4000-8000-0000000000c1",
      },
    ],
    outcome: "answered",
    phase: "done",
    replaced: false,
    errorMessage: null,
    feedback: null,
    retryText: pt.ask.suggestions[0].question,
  },
]

const meta = {
  title: "Patterns/ChatThread",
  component: ChatThread,
  args: {
    messages,
    live: "O horário de visita é das 11:00 às 20:00.",
    onFeedback: () => undefined,
    onRetry: () => undefined,
  },
} satisfies Meta<typeof ChatThread>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {}
