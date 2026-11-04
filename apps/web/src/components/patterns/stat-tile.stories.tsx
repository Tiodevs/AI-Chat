import type { Meta, StoryObj } from "@storybook/react-vite"

import { StatTile } from "@/components/patterns/stat-tile.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "Patterns/StatTile",
  component: StatTile,
  args: { label: pt.documents.status.ready, value: "12" },
} satisfies Meta<typeof StatTile>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  render: () => (
    <div className="grid max-w-xl grid-cols-3 gap-2">
      <StatTile label={pt.documents.status.ready} value="12" detail="80%" tone="success" />
      <StatTile label={pt.documents.status.processing} value="2" detail="13%" tone="info" />
      <StatTile label={pt.documents.status.failed} value="1" detail="7%" tone="danger" />
      <StatTile label={pt.insights.outcomes.abstained} value="4" tone="warning" />
      <StatTile label={pt.insights.feedback.none} value="0" />
    </div>
  ),
}
