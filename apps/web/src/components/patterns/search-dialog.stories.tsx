import type { Meta, StoryObj } from "@storybook/react-vite"

import { SearchDialog } from "@/components/patterns/search-dialog.tsx"

const meta = {
  title: "Patterns/SearchDialog",
  component: SearchDialog,
} satisfies Meta<typeof SearchDialog>

export default meta

type Story = StoryObj<typeof meta>

export const Aberto: Story = {
  args: {
    open: true,
    onOpenChange: () => undefined,
  },
}

export const Fechado: Story = {
  args: {
    open: false,
    onOpenChange: () => undefined,
  },
}
