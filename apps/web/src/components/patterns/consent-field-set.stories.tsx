import { useState } from "react"
import type { Meta, StoryObj } from "@storybook/react-vite"

import { ConsentFieldSet } from "@/components/patterns/consent-field-set.tsx"
import { pt } from "@/i18n/pt.ts"
import {
  consentIssues,
  emptyConsents,
  type Consents,
} from "@/features/registration/model.ts"

const meta = {
  title: "Patterns/ConsentFieldSet",
  component: ConsentFieldSet,
} satisfies Meta<typeof ConsentFieldSet>

export default meta

type Story = StoryObj<typeof meta>

const empty = emptyConsents()

export const Estados: Story = {
  args: {
    value: empty,
    onChange: () => undefined,
    errors: {},
    disabled: false,
  },
  render: () => (
    <div className="flex max-w-xl flex-col gap-8">
      <ConsentPreview />
      <ConsentFieldSet
        value={empty}
        onChange={() => undefined}
        errors={consentIssues(empty)}
        disabled={false}
      />
      <ConsentFieldSet
        value={{ ...empty, accept_terms: true, age_18_plus: true }}
        onChange={() => undefined}
        errors={{}}
        disabled
      />
      <p className="text-caption text-danger">
        {pt.registration.termsRequired}
      </p>
    </div>
  ),
}

function ConsentPreview() {
  const [value, setValue] = useState<Consents>(empty)
  return (
    <ConsentFieldSet
      value={value}
      onChange={setValue}
      errors={{}}
      disabled={false}
    />
  )
}
