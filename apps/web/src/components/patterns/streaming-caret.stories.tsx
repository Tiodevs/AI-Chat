import type { Meta, StoryObj } from "@storybook/react-vite"

import { StreamingCaret } from "@/components/patterns/streaming-caret.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "Patterns/StreamingCaret",
  component: StreamingCaret,
} satisfies Meta<typeof StreamingCaret>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  render: () => (
    <p className="text-message text-foreground" aria-busy="true">
      {pt.ask.waiting}
      <StreamingCaret />
    </p>
  ),
}
