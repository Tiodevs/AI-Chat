import type { Meta, StoryObj } from "@storybook/react-vite"

import { CitationChip } from "@/components/patterns/citation-chip.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "Patterns/CitationChip",
  component: CitationChip,
  args: { index: 1, onSelect: () => undefined },
} satisfies Meta<typeof CitationChip>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  render: () => (
    <div className="flex flex-wrap items-center gap-3">
      <CitationChip index={1} onSelect={() => undefined} />
      <CitationChip index={2} onSelect={() => undefined} />
      <span id="chip-error" className="text-caption text-danger">
        {pt.couldNotContinue}
      </span>
      <CitationChip index={3} onSelect={() => undefined} />
    </div>
  ),
}
