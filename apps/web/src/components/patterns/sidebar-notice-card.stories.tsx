import type { Meta, StoryObj } from "@storybook/react-vite"

import { SidebarNoticeCard } from "@/components/patterns/sidebar-notice-card.tsx"

const meta = {
  title: "Patterns/SidebarNoticeCard",
  component: SidebarNoticeCard,
} satisfies Meta<typeof SidebarNoticeCard>

export default meta

type Story = StoryObj<typeof meta>

export const Padrao: Story = {
  render: () => (
    <div className="w-60">
      <SidebarNoticeCard />
    </div>
  ),
}
