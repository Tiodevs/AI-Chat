import { useState } from "react"
import type { Meta, StoryObj } from "@storybook/react-vite"

import { Composer } from "@/components/patterns/composer.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "Patterns/Composer",
  component: Composer,
} satisfies Meta<typeof Composer>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  args: {
    value: "",
    onChange: () => undefined,
    onSubmit: () => undefined,
    onStop: () => undefined,
    streaming: false,
    pending: false,
    disabled: false,
    disabledReason: null,
    error: null,
  },
  render: () => (
    <div className="flex max-w-xl flex-col gap-8">
      <ComposerPreview />
      <Composer
        value={pt.ask.suggestions[0].question}
        onChange={() => undefined}
        onSubmit={() => undefined}
        onStop={() => undefined}
        streaming
        pending={false}
        disabled={false}
        disabledReason={null}
        error={null}
      />
      <Composer
        value=""
        onChange={() => undefined}
        onSubmit={() => undefined}
        onStop={() => undefined}
        streaming={false}
        pending
        disabled={false}
        disabledReason={null}
        error={null}
      />
      <Composer
        value=""
        onChange={() => undefined}
        onSubmit={() => undefined}
        onStop={() => undefined}
        streaming={false}
        pending={false}
        disabled
        disabledReason={pt.ask.unavailable}
        error={null}
      />
      <Composer
        value=" "
        onChange={() => undefined}
        onSubmit={() => undefined}
        onStop={() => undefined}
        streaming={false}
        pending={false}
        disabled={false}
        disabledReason={null}
        error={pt.couldNotContinue}
      />
    </div>
  ),
}

function ComposerPreview() {
  const [value, setValue] = useState<string>(pt.ask.suggestions[0].question)
  return (
    <Composer
      value={value}
      onChange={setValue}
      onSubmit={() => undefined}
      onStop={() => undefined}
      streaming={false}
      pending={false}
      disabled={false}
      disabledReason={null}
      error={null}
    />
  )
}
