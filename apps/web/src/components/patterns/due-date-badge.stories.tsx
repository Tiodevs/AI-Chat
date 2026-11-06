import type { Meta, StoryObj } from "@storybook/react-vite"

import { DueDateBadge } from "@/components/patterns/due-date-badge.tsx"

const now = "2031-01-15T12:00:00Z"

const meta = {
  title: "Patterns/DueDateBadge",
  component: DueDateBadge,
  args: { dueAt: "2031-01-25T12:00:00Z", now },
} satisfies Meta<typeof DueDateBadge>

export default meta

type Story = StoryObj<typeof meta>

/** Atrasado em `--danger`, prazo próximo em `--warning`, no prazo e fechado em neutro. */
export const Estados: Story = {
  render: () => (
    <div className="flex flex-col items-start gap-4">
      <DueDateBadge dueAt="2031-01-10T12:00:00Z" now={now} />
      <DueDateBadge dueAt="2031-01-15T09:00:00Z" now={now} />
      <DueDateBadge dueAt="2031-01-15T18:00:00Z" now={now} />
      <DueDateBadge dueAt="2031-01-17T12:00:00Z" now={now} />
      <DueDateBadge dueAt="2031-01-25T12:00:00Z" now={now} />
      <DueDateBadge dueAt="2031-01-20T12:00:00Z" closedAt="2031-01-12T15:00:00Z" now={now} />
    </div>
  ),
}

export const Atrasado: Story = { args: { dueAt: "2031-01-10T12:00:00Z" } }

export const PrazoProximo: Story = { args: { dueAt: "2031-01-17T12:00:00Z" } }

export const Fechado: Story = {
  args: { dueAt: "2031-01-20T12:00:00Z", closedAt: "2031-01-12T15:00:00Z" },
}
