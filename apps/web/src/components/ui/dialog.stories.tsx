import type { Meta, StoryObj } from "@storybook/react-vite"

import { Button } from "@/components/ui/button.tsx"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "UI/Dialog",
  component: Dialog,
} satisfies Meta<typeof Dialog>

export default meta

type Story = StoryObj<typeof meta>

export const Aberto: Story = {
  render: () => (
    <Dialog open>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{pt.sidebar.search}</DialogTitle>
          <DialogDescription>{pt.sidebar.searchDescription}</DialogDescription>
        </DialogHeader>
      </DialogContent>
    </Dialog>
  ),
}

export const Fechado: Story = {
  render: () => (
    <Dialog>
      <DialogTrigger asChild>
        <Button>{pt.sidebar.search}</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{pt.sidebar.search}</DialogTitle>
          <DialogDescription>{pt.sidebar.searchDescription}</DialogDescription>
        </DialogHeader>
      </DialogContent>
    </Dialog>
  ),
}
