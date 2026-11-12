import type { Meta, StoryObj } from "@storybook/react-vite"

import { HandoffStatusBar } from "@/components/patterns/handoff-status-bar.tsx"

const meta = {
  title: "Patterns/HandoffStatusBar",
  component: HandoffStatusBar,
  args: { status: "queued", queuePosition: 2, onEnd: () => undefined },
} satisfies Meta<typeof HandoffStatusBar>

export default meta

type Story = StoryObj<typeof meta>

// Na fila, devolvido à fila, em atendimento, reconectando e encerrando.
export const Estados: Story = {
  render: () => (
    <div className="flex max-w-xl flex-col gap-6">
      <HandoffStatusBar
        status="queued"
        queuePosition={2}
        onEnd={() => undefined}
      />
      <HandoffStatusBar
        status="queued"
        queuePosition={1}
        returned
        onEnd={() => undefined}
      />
      <HandoffStatusBar
        status="assigned"
        queuePosition={null}
        onEnd={() => undefined}
      />
      <HandoffStatusBar
        status="assigned"
        queuePosition={null}
        reconnecting
        onEnd={() => undefined}
      />
      <HandoffStatusBar
        status="assigned"
        queuePosition={null}
        pending
        onEnd={() => undefined}
      />
    </div>
  ),
}
