import type { Meta, StoryObj } from "@storybook/react-vite"

import { Progress } from "@/components/ui/progress.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "UI/Progress",
  component: Progress,
  args: { value: 40, "aria-label": pt.insights.budget.label },
} satisfies Meta<typeof Progress>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  render: () => (
    <div className="flex max-w-sm flex-col gap-4">
      <Progress value={0} aria-label={pt.insights.budget.label} />
      <Progress value={40} aria-label={pt.insights.budget.label} />
      <Progress
        value={85}
        aria-label={pt.insights.budget.label}
        className="[&>[data-slot=progress-indicator]]:bg-warning"
      />
    </div>
  ),
}
