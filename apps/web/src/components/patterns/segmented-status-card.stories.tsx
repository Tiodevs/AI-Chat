import type { Meta, StoryObj } from "@storybook/react-vite"

import { SegmentedStatusCard } from "@/components/patterns/segmented-status-card.tsx"
import { pt } from "@/i18n/pt.ts"

const t = pt.insights

const meta = {
  title: "Patterns/SegmentedStatusCard",
  component: SegmentedStatusCard,
  args: {
    title: t.outcomesCard.title,
    emptyText: t.outcomesCard.empty,
    views: [
      {
        key: "outcome",
        label: t.outcomesCard.outcome,
        segments: [
          { key: "answered", label: t.outcomes.answered, count: 42, tone: "success" },
          { key: "abstained", label: t.outcomes.abstained, count: 9, tone: "warning" },
          { key: "refused", label: t.outcomes.refused, count: 3, tone: "danger" },
          { key: "off_topic", label: t.outcomes.off_topic, count: 5, tone: "neutral" },
        ],
      },
      {
        key: "feedback",
        label: t.outcomesCard.feedback,
        segments: [
          { key: "helpful", label: t.feedback.helpful, count: 20, tone: "success" },
          { key: "not_helpful", label: t.feedback.not_helpful, count: 4, tone: "danger" },
          { key: "none", label: t.feedback.none, count: 35, tone: "neutral" },
        ],
      },
    ],
  },
} satisfies Meta<typeof SegmentedStatusCard>

export default meta

type Story = StoryObj<typeof meta>

export const ComAbas: Story = {}

export const Vazio: Story = {
  args: {
    views: [{ key: "outcome", label: t.outcomesCard.outcome, segments: [] }],
  },
}
