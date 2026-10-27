import type { Meta, StoryObj } from "@storybook/react-vite"

import { Button } from "@/components/ui/button.tsx"
import { Spinner } from "@/components/ui/spinner.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "UI/Spinner",
  component: Spinner,
} satisfies Meta<typeof Spinner>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  render: () => (
    <div className="flex flex-wrap items-center gap-3">
      <Spinner />
      <Button disabled aria-busy="true">
        <Spinner aria-hidden data-icon="inline-start" />
        {pt.signIn.pending}
      </Button>
      <Button disabled>
        <Spinner aria-hidden data-icon="inline-start" />
        {pt.signIn.pending}
      </Button>
    </div>
  ),
}
