import type { Meta, StoryObj } from "@storybook/react-vite"

import { Input } from "@/components/ui/input.tsx"
import { Label } from "@/components/ui/label.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "UI/Label",
  component: Label,
} satisfies Meta<typeof Label>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  render: () => (
    <div className="flex w-80 flex-col gap-3">
      <Label htmlFor="label-rest">{pt.signIn.email}</Label>
      <Input id="label-rest" type="email" />
      <Label htmlFor="label-focus">{pt.signIn.email}</Label>
      <Input id="label-focus" type="email" autoFocus defaultValue="ada@example.com" />
      <Label htmlFor="label-disabled">{pt.signIn.email}</Label>
      <Input id="label-disabled" type="email" disabled defaultValue="ada@example.com" />
      <Label htmlFor="label-invalid">{pt.signIn.email}</Label>
      <Input id="label-invalid" type="email" aria-invalid="true" defaultValue="ada" />
    </div>
  ),
}
