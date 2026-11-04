import type { Meta, StoryObj } from "@storybook/react-vite"

import { GroupedBarCard } from "@/components/patterns/grouped-bar-card.tsx"
import { pt } from "@/i18n/pt.ts"

const f = pt.insights.funnel

const meta = {
  title: "Patterns/GroupedBarCard",
  component: GroupedBarCard,
  args: {
    title: f.title,
    rows: [
      { key: "started", label: f.steps.started, first: 40, second: 18 },
      { key: "password_set", label: f.steps.password_set, first: 28, second: 18 },
      { key: "completed", label: f.steps.completed, first: 24, second: 17 },
    ],
    firstLabel: f.chat,
    secondLabel: f.form,
    categoryLabel: f.step,
    tableCaption: f.tableCaption,
  },
} satisfies Meta<typeof GroupedBarCard>

export default meta

type Story = StoryObj<typeof meta>

export const ComDados: Story = {}

export const Vazio: Story = {
  args: {
    rows: [
      { key: "started", label: f.steps.started, first: 0, second: 0 },
      { key: "completed", label: f.steps.completed, first: 0, second: 0 },
    ],
  },
}
