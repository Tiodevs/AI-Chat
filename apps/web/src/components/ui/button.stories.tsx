import type { Meta, StoryObj } from "@storybook/react-vite"

import { Button } from "@/components/ui/button.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "UI/Button",
  component: Button,
} satisfies Meta<typeof Button>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  render: () => (
    <div className="flex flex-wrap items-center gap-3">
      <Button>{pt.nav.signIn}</Button>
      <Button aria-pressed="true">{pt.nav.signIn}</Button>
      <Button autoFocus>{pt.nav.signIn}</Button>
      <Button disabled>{pt.nav.signIn}</Button>
      <Button aria-invalid="true" aria-describedby="button-error">
        {pt.nav.signIn}
      </Button>
      <Button disabled aria-busy="true">
        {pt.loading}
      </Button>
      <p id="button-error" className="text-caption text-danger">
        {pt.couldNotContinue}
      </p>
    </div>
  ),
}
