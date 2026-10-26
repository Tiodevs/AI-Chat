import type { Meta, StoryObj } from "@storybook/react-vite"

import { Button } from "@/components/ui/button.tsx"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "UI/DropdownMenu",
  component: DropdownMenu,
} satisfies Meta<typeof DropdownMenu>

export default meta

type Story = StoryObj<typeof meta>

function Menu({ open }: { open?: boolean }) {
  return (
    <DropdownMenu open={open}>
      <DropdownMenuTrigger asChild>
        <Button>{pt.profile.menu}</Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuGroup>
          <DropdownMenuItem>{pt.nav.accountPage}</DropdownMenuItem>
          <DropdownMenuItem disabled>{pt.nav.signIn}</DropdownMenuItem>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export const Aberto: Story = {
  render: () => <Menu open />,
}

export const Fechado: Story = {
  render: () => <Menu />,
}
