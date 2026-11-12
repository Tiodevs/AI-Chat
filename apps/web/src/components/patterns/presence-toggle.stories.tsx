import type { Meta, StoryObj } from "@storybook/react-vite"

import { PresenceToggle } from "@/components/patterns/presence-toggle.tsx"

const meta = {
  title: "Patterns/PresenceToggle",
  component: PresenceToggle,
  args: { value: "available", onChange: () => undefined },
} satisfies Meta<typeof PresenceToggle>

export default meta

type Story = StoryObj<typeof meta>

// Disponível, Ausente e a troca em andamento.
export const Estados: Story = {
  render: () => (
    <div className="flex flex-col gap-6">
      <PresenceToggle value="available" onChange={() => undefined} />
      <PresenceToggle value="away" onChange={() => undefined} />
      <PresenceToggle value="available" pending onChange={() => undefined} />
    </div>
  ),
}
