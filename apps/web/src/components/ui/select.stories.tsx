import type { Meta, StoryObj } from "@storybook/react-vite"

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "UI/Select",
  component: Select,
} satisfies Meta<typeof Select>

export default meta

type Story = StoryObj<typeof meta>

function Example({ id, disabled = false }: { id: string; disabled?: boolean }) {
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-label text-muted-foreground">
        {pt.quality.filters.outcome}
      </label>
      <Select defaultValue="all" disabled={disabled}>
        <SelectTrigger id={id} className="min-w-56">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">{pt.quality.filters.anyOutcome}</SelectItem>
          <SelectItem value="answered">{pt.insights.outcomes.answered}</SelectItem>
          <SelectItem value="abstained">{pt.insights.outcomes.abstained}</SelectItem>
        </SelectContent>
      </Select>
    </div>
  )
}

export const Estados: Story = {
  render: () => (
    <div className="flex flex-col gap-6">
      <Example id="select-rest" />
      <Example id="select-disabled" disabled />
    </div>
  ),
}
