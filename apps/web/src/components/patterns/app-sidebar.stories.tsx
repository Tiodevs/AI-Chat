import type { Meta, StoryObj } from "@storybook/react-vite"

import { AppSidebar } from "@/components/patterns/app-sidebar.tsx"

const meta = {
  title: "Patterns/AppSidebar",
  component: AppSidebar,
} satisfies Meta<typeof AppSidebar>

export default meta

type Story = StoryObj<typeof meta>

export const Expandida: Story = {
  args: {
    collapsed: false,
    onToggleCollapsed: () => undefined,
    onSearch: () => undefined,
  },
  render: (args) => (
    <div className="h-[40rem]">
      <AppSidebar {...args} />
    </div>
  ),
}

export const Recolhida: Story = {
  args: {
    collapsed: true,
    onToggleCollapsed: () => undefined,
    onSearch: () => undefined,
  },
  render: (args) => (
    <div className="h-[40rem]">
      <AppSidebar {...args} />
    </div>
  ),
}
