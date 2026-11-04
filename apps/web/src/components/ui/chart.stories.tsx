import type { Meta, StoryObj } from "@storybook/react-vite"
import { Bar, BarChart, XAxis } from "recharts"

import { ChartContainer, type ChartConfig } from "@/components/ui/chart.tsx"
import { pt } from "@/i18n/pt.ts"

const config = {
  value: { label: pt.insights.trend.questions, color: "var(--chart-1)" },
} satisfies ChartConfig

const data = [
  { label: "seg", value: 12 },
  { label: "ter", value: 18 },
  { label: "qua", value: 9 },
]

const meta = {
  title: "UI/Chart",
  component: ChartContainer,
  args: { config, children: <BarChart data={data} /> },
} satisfies Meta<typeof ChartContainer>

export default meta

type Story = StoryObj<typeof meta>

export const Barras: Story = {
  render: () => (
    <div className="max-w-md" aria-hidden="true">
      <ChartContainer config={config} className="aspect-auto h-48 w-full">
        <BarChart data={data}>
          <XAxis dataKey="label" tickLine={false} axisLine={false} />
          <Bar dataKey="value" fill="var(--color-value)" radius={4} isAnimationActive={false} />
        </BarChart>
      </ChartContainer>
    </div>
  ),
}
