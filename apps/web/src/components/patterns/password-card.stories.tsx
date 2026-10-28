import { useState } from "react"
import type { Meta, StoryObj } from "@storybook/react-vite"

import { PasswordCard } from "@/components/patterns/password-card.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "Patterns/PasswordCard",
  component: PasswordCard,
} satisfies Meta<typeof PasswordCard>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  args: {
    value: "",
    onChange: () => undefined,
    pending: false,
    error: null,
    moveFocus: false,
  },
  render: () => (
    <div className="flex max-w-md flex-col gap-6">
      <PasswordPreview />
      <PasswordCard
        value="curta"
        onChange={() => undefined}
        pending={false}
        error={pt.registration.passwordInvalid}
        moveFocus={false}
        onSubmit={() => undefined}
      />
      <PasswordCard
        value="senha-segura-1"
        onChange={() => undefined}
        pending
        error={null}
        moveFocus={false}
        onSubmit={() => undefined}
      />
      <PasswordCard
        value=""
        onChange={() => undefined}
        pending={false}
        error={null}
        moveFocus
        onSubmit={() => undefined}
      />
    </div>
  ),
}

function PasswordPreview() {
  const [value, setValue] = useState("")
  return (
    <PasswordCard
      value={value}
      onChange={setValue}
      pending={false}
      error={null}
      moveFocus={false}
      onSubmit={() => undefined}
    />
  )
}
