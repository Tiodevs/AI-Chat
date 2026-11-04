import type { Meta, StoryObj } from "@storybook/react-vite"

import { GuestHeader } from "@/components/patterns/guest-header.tsx"

const meta = {
  title: "Patterns/GuestHeader",
  component: GuestHeader,
} satisfies Meta<typeof GuestHeader>

export default meta

type Story = StoryObj<typeof meta>

export const Largo: Story = {
  args: { compact: false },
}

export const Celular: Story = {
  args: { compact: true },
  render: (args) => (
    <div className="max-w-[375px]">
      <GuestHeader {...args} />
    </div>
  ),
}
