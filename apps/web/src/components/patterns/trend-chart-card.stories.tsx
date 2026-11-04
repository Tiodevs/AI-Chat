import type { Meta, StoryObj } from "@storybook/react-vite"
import { useState } from "react"

import { TrendChartCard } from "@/components/patterns/trend-chart-card.tsx"
import { pt } from "@/i18n/pt.ts"

const t = pt.insights

const questions = [12, 18, 9, 22, 30, 25, 17, 21]
const answered = [8, 12, 6, 15, 21, 19, 11, 14]

const points = questions.map((value, index) => ({
  key: `2031-01-${String(8 + index)}`,
  label: `${String(8 + index)} jan.`,
  primary: value,
  secondary: answered[index] ?? 0,
}))

const periods = [
  { value: "7", label: t.period.days7 },
  { value: "30", label: t.period.days30 },
]

function Interactive() {
  const [period, setPeriod] = useState("7")
  return (
    <TrendChartCard
      title={t.trend.title}
      points={points}
      primaryLabel={t.trend.questions}
      secondaryLabel={t.trend.answered}
      dateLabel={t.trend.date}
      tableCaption={t.trend.tableCaption}
      periodLabel={t.period.label}
      periods={periods}
      period={period}
      onPeriodChange={setPeriod}
    />
  )
}

const meta = {
  title: "Patterns/TrendChartCard",
  component: TrendChartCard,
  args: {
    title: t.trend.title,
    points,
    primaryLabel: t.trend.questions,
    secondaryLabel: t.trend.answered,
    dateLabel: t.trend.date,
    tableCaption: t.trend.tableCaption,
    periodLabel: t.period.label,
    periods,
    period: "7",
    onPeriodChange: () => undefined,
  },
} satisfies Meta<typeof TrendChartCard>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  render: () => (
    <div className="max-w-3xl">
      <Interactive />
    </div>
  ),
}
