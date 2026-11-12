import type { Meta, StoryObj } from "@storybook/react-vite"

import { RedactDialog } from "@/components/patterns/redact-dialog.tsx"

const meta = {
  title: "Patterns/RedactDialog",
  component: RedactDialog,
  args: {
    open: true,
    onOpenChange: () => undefined,
    onConfirm: () => undefined,
  },
} satisfies Meta<typeof RedactDialog>

export default meta

type Story = StoryObj<typeof meta>

export const Padrao: Story = {}

export const Removendo: Story = { args: { pending: true } }
