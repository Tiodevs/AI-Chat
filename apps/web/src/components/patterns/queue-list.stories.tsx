import type { Meta, StoryObj } from "@storybook/react-vite"

import {
  QueueList,
  type QueueItemView,
} from "@/components/patterns/queue-list.tsx"

const now = new Date("2026-11-12T15:10:00Z")

const items: QueueItemView[] = [
  {
    handoffId: "a1",
    label: "Visitante 3f9a1c22",
    queuedAt: "2026-11-12T15:09:40Z",
    trigger: "abstained",
    returned: false,
    visitorPresent: true,
  },
  {
    handoffId: "a2",
    label: "Visitante 7be04d91",
    queuedAt: "2026-11-12T15:04:00Z",
    trigger: "not_helpful",
    returned: true,
    visitorPresent: true,
  },
  {
    handoffId: "a3",
    label: "Visitante c0d5e8f1",
    queuedAt: "2026-11-12T15:01:00Z",
    trigger: "degraded",
    returned: false,
    visitorPresent: false,
  },
]

const meta = {
  title: "Patterns/QueueList",
  component: QueueList,
  args: { items, now, canTake: true, onTake: () => undefined },
} satisfies Meta<typeof QueueList>

export default meta

type Story = StoryObj<typeof meta>

export const ComFila: Story = {}

export const Assumindo: Story = { args: { pendingId: "a2" } }

export const SemCapacidade: Story = { args: { canTake: false } }

export const Vazia: Story = { args: { items: [] } }

// Um atendimento do WhatsApp mostra o selo do canal, sem o número (seção 30.11).
export const ComWhatsApp: Story = {
  args: {
    items: [
      { ...items[0], handoffId: "w1", channel: "whatsapp" },
      ...items.slice(1),
    ],
  },
}
