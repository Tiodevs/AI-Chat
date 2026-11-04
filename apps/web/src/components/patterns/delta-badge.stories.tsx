import type { Meta, StoryObj } from "@storybook/react-vite"

import { DeltaBadge } from "@/components/patterns/delta-badge.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "Patterns/DeltaBadge",
  component: DeltaBadge,
  args: { direction: "up", text: pt.insights.delta.up.replace("{value}", "12%") },
} satisfies Meta<typeof DeltaBadge>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  render: () => (
    <div className="flex flex-col items-start gap-3">
      <DeltaBadge direction="up" text={pt.insights.delta.up.replace("{value}", "12%")} />
      <DeltaBadge direction="down" text={pt.insights.delta.down.replace("{value}", "3 p.p.")} />
      <DeltaBadge
        direction="down"
        goodWhen="down"
        text={pt.insights.delta.down.replace("{value}", "3 p.p.")}
      />
      <DeltaBadge direction="flat" text={pt.insights.delta.flat} />
      <DeltaBadge direction="none" text={pt.insights.delta.none} />
    </div>
  ),
}
