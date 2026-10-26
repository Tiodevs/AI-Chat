import type { Meta, StoryObj } from "@storybook/react-vite"

import { Button } from "@/components/ui/button.tsx"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "UI/Sheet",
  component: Sheet,
} satisfies Meta<typeof Sheet>

export default meta

type Story = StoryObj<typeof meta>

export const Aberto: Story = {
  render: () => (
    <Sheet open>
      <SheetContent side="left" className="bg-shell">
        <SheetHeader>
          <SheetTitle>{pt.sidebar.label}</SheetTitle>
        </SheetHeader>
      </SheetContent>
    </Sheet>
  ),
}

export const Fechado: Story = {
  render: () => (
    <Sheet>
      <SheetTrigger asChild>
        <Button>{pt.sidebar.openMenu}</Button>
      </SheetTrigger>
      <SheetContent side="left" className="bg-shell">
        <SheetHeader>
          <SheetTitle>{pt.sidebar.label}</SheetTitle>
        </SheetHeader>
      </SheetContent>
    </Sheet>
  ),
}
