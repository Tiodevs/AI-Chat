import type { Meta, StoryObj } from "@storybook/react-vite"

import { Input } from "@/components/ui/input.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "UI/Input",
  component: Input,
} satisfies Meta<typeof Input>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  render: () => (
    <div className="flex w-80 flex-col gap-3">
      <Input aria-label={pt.sidebar.search} placeholder={pt.sidebar.searchPlaceholder} />
      <Input autoFocus aria-label={pt.sidebar.search} defaultValue={pt.nav.privacy} />
      <Input disabled aria-label={pt.sidebar.search} defaultValue={pt.nav.privacy} />
      <Input
        aria-invalid="true"
        aria-label={pt.sidebar.search}
        aria-describedby="input-error"
        defaultValue="?"
      />
      <p id="input-error" className="text-caption text-danger">
        {pt.pageNotFound}
      </p>
    </div>
  ),
}
