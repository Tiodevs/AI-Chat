import type { Meta, StoryObj } from "@storybook/react-vite"

import { SafetyNotice } from "@/components/patterns/safety-notice.tsx"

const meta = {
  title: "Patterns/SafetyNotice",
  component: SafetyNotice,
} satisfies Meta<typeof SafetyNotice>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  render: () => (
    <div className="max-w-xl">
      <SafetyNotice />
    </div>
  ),
}
