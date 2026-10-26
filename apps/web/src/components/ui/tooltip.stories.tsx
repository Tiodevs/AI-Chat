import type { Meta, StoryObj } from "@storybook/react-vite"

import { Button } from "@/components/ui/button.tsx"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "UI/Tooltip",
  component: Tooltip,
} satisfies Meta<typeof Tooltip>

export default meta

type Story = StoryObj<typeof meta>

export const Aberto: Story = {
  render: () => (
    <Tooltip open>
      <TooltipTrigger asChild>
        <Button>{pt.sidebar.search}</Button>
      </TooltipTrigger>
      <TooltipContent>{pt.sidebar.search}</TooltipContent>
    </Tooltip>
  ),
}

export const Fechado: Story = {
  render: () => (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button disabled>{pt.sidebar.search}</Button>
      </TooltipTrigger>
      <TooltipContent>{pt.sidebar.search}</TooltipContent>
    </Tooltip>
  ),
}
