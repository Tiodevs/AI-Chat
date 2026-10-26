import type { Meta, StoryObj } from "@storybook/react-vite"

import { Separator } from "@/components/ui/separator.tsx"

const meta = {
  title: "UI/Separator",
  component: Separator,
} satisfies Meta<typeof Separator>

export default meta

type Story = StoryObj<typeof meta>

export const Horizontal: Story = {
  render: () => (
    <div className="w-64">
      <Separator />
    </div>
  ),
}
