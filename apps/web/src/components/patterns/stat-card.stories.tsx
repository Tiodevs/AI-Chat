import type { Meta, StoryObj } from "@storybook/react-vite"

import { StatCard } from "@/components/patterns/stat-card.tsx"
import { pt } from "@/i18n/pt.ts"

const count = (value: number) => value.toLocaleString("pt-BR")
const percent = (value: number) =>
  value.toLocaleString("pt-BR", { style: "percent", maximumFractionDigits: 1 })

const meta = {
  title: "Patterns/StatCard",
  component: StatCard,
  args: {
    label: pt.insights.stats.questions,
    value: 1234,
    format: count,
    delta: { direction: "up", text: pt.insights.delta.up.replace("{value}", "23,4%") },
    caption: pt.insights.period.comparedTo.replace("{days}", "7"),
    emptyText: pt.insights.notAvailable,
    ariaLabel: "Perguntas: 1.234",
  },
} satisfies Meta<typeof StatCard>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  render: (args) => (
    <div className="grid max-w-3xl grid-cols-2 gap-4">
      <StatCard {...args} />
      <StatCard
        {...args}
        label={pt.insights.stats.abstentionRate}
        value={0.25}
        format={percent}
        decimals={3}
        goodWhen="down"
        delta={{ direction: "up", text: pt.insights.delta.up.replace("{value}", "5 p.p.") }}
        ariaLabel="Taxa de abstenção: 25%"
      />
      <StatCard
        {...args}
        label={pt.insights.stats.helpfulRate}
        value={null}
        delta={{ direction: "none", text: pt.insights.delta.none }}
        ariaLabel="Taxa de útil: sem dados"
      />
      <StatCard {...args} loading ariaLabel={pt.loading} />
    </div>
  ),
}
