import type { Meta, StoryObj } from "@storybook/react-vite"

import {
  OutcomeBadge,
  type OutcomeKind,
} from "@/components/patterns/outcome-badge.tsx"

const kinds: OutcomeKind[] = [
  "answered",
  "abstained",
  "refused",
  "replaced",
  "unavailable",
]

const meta = {
  title: "Patterns/OutcomeBadge",
  component: OutcomeBadge,
  args: { kind: "answered" },
} satisfies Meta<typeof OutcomeBadge>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  render: () => (
    <div className="flex flex-col items-start gap-3">
      {kinds.map((kind) => (
        <OutcomeBadge key={kind} kind={kind} />
      ))}
    </div>
  ),
}
