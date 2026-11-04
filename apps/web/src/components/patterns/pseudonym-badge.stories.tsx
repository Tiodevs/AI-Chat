import type { Meta, StoryObj } from "@storybook/react-vite"

import { PseudonymBadge } from "@/components/patterns/pseudonym-badge.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "Patterns/PseudonymBadge",
  component: PseudonymBadge,
  args: { kind: "member", pseudonym: "e5f6a7b8", kindLabel: pt.quality.subject.member },
} satisfies Meta<typeof PseudonymBadge>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  render: () => (
    <div className="flex flex-col items-start gap-3">
      <PseudonymBadge kind="member" pseudonym="e5f6a7b8" kindLabel={pt.quality.subject.member} />
      <PseudonymBadge kind="guest" pseudonym="a1b2c3d4" kindLabel={pt.quality.subject.guest} />
    </div>
  ),
}
