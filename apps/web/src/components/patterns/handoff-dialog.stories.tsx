import type { Meta, StoryObj } from "@storybook/react-vite"

import { HandoffDialog } from "@/components/patterns/handoff-dialog.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "Patterns/HandoffDialog",
  component: HandoffDialog,
  args: {
    open: true,
    onOpenChange: () => undefined,
    onConfirm: () => undefined,
    pending: false,
    error: null,
  },
} satisfies Meta<typeof HandoffDialog>

export default meta

type Story = StoryObj<typeof meta>

export const Padrao: Story = {}

export const Chamando: Story = { args: { pending: true } }

export const ComErro: Story = { args: { error: pt.couldNotContinue } }
