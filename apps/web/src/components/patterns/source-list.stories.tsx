import { useState } from "react"
import type { Meta, StoryObj } from "@storybook/react-vite"

import { SourceList } from "@/components/patterns/source-list.tsx"
import type { CitationView } from "@/features/ask/types.ts"

const citations: CitationView[] = [
  {
    index: 1,
    documentTitle: "Visitas",
    heading: "Horário",
    chunkId: "00000000-0000-4000-8000-0000000000c1",
  },
  {
    index: 2,
    documentTitle: "Estacionamento",
    heading: null,
    chunkId: "00000000-0000-4000-8000-0000000000c2",
  },
]

const meta = {
  title: "Patterns/SourceList",
  component: SourceList,
  args: { citations, open: true, onOpenChange: () => undefined },
} satisfies Meta<typeof SourceList>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  render: () => <SourceListPreview />,
}

function SourceListPreview() {
  const [open, setOpen] = useState(true)
  return (
    <div className="flex max-w-md flex-col gap-6">
      <SourceList citations={citations} open={open} onOpenChange={setOpen} />
      <SourceList
        citations={citations}
        open={false}
        onOpenChange={() => undefined}
      />
    </div>
  )
}
