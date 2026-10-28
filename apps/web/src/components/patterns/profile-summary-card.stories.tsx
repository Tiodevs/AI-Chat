import { useState } from "react"
import type { Meta, StoryObj } from "@storybook/react-vite"

import { ProfileSummaryCard } from "@/components/patterns/profile-summary-card.tsx"
import { pt } from "@/i18n/pt.ts"
import {
  emptyFields,
  type RegistrationFields,
} from "@/features/registration/model.ts"

const filled: RegistrationFields = {
  full_name: "Ana Costa",
  email: "ana@example.com",
  phone: null,
  visitor_type: "visitor",
  visit_reason: null,
}

const meta = {
  title: "Patterns/ProfileSummaryCard",
  component: ProfileSummaryCard,
} satisfies Meta<typeof ProfileSummaryCard>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  args: {
    fields: emptyFields(),
    fieldErrors: {},
    pending: false,
    onEdit: async () => true,
  },
  render: () => (
    <div className="flex max-w-md flex-col gap-6">
      <ProfileSummaryCard
        fields={emptyFields()}
        fieldErrors={{}}
        pending={false}
        onEdit={async () => true}
      />
      <ProfileSummaryCard
        fields={filled}
        fieldErrors={{}}
        pending={false}
        onEdit={async () => true}
      />
      <ProfileSummaryCard
        fields={{ ...filled, email: "ada" }}
        fieldErrors={{ email: pt.registration.emailInvalid }}
        pending={false}
        onEdit={async () => true}
      />
      <ProfileSummaryCard
        fields={{ ...filled, email: "ana@example.com" }}
        fieldErrors={{
          email: "Este e-mail já tem uma conta. Entre para continuar.",
        }}
        pending={false}
        onEdit={async () => true}
      />
      <EditableSummary />
      <ProfileSummaryCard
        fields={filled}
        fieldErrors={{}}
        pending
        onEdit={async () => true}
      />
    </div>
  ),
}

function EditableSummary() {
  const [fields, setFields] = useState(filled)
  return (
    <ProfileSummaryCard
      fields={fields}
      fieldErrors={{}}
      pending={false}
      onEdit={async (field, value) => {
        setFields((current) => ({ ...current, [field]: value }))
        return true
      }}
    />
  )
}
