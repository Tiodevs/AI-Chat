import type { Meta, StoryObj } from "@storybook/react-vite"

import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field.tsx"
import { Input } from "@/components/ui/input.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "UI/Field",
  component: Field,
} satisfies Meta<typeof Field>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  render: () => (
    <FieldGroup className="w-80">
      <Field>
        <FieldLabel htmlFor="field-rest">{pt.signIn.email}</FieldLabel>
        <Input id="field-rest" type="email" autoComplete="email" />
      </Field>
      <Field>
        <FieldLabel htmlFor="field-focus">{pt.signIn.email}</FieldLabel>
        <Input id="field-focus" type="email" autoComplete="email" autoFocus defaultValue="ada@example.com" />
      </Field>
      <Field data-disabled>
        <FieldLabel htmlFor="field-disabled">{pt.signIn.email}</FieldLabel>
        <Input id="field-disabled" type="email" disabled defaultValue="ada@example.com" />
      </Field>
      <Field data-invalid>
        <FieldLabel htmlFor="field-invalid">{pt.signIn.email}</FieldLabel>
        <Input
          id="field-invalid"
          type="email"
          aria-invalid="true"
          aria-describedby="field-invalid-error"
          defaultValue="ada"
        />
        <FieldError id="field-invalid-error">{pt.signIn.emailInvalid}</FieldError>
      </Field>
    </FieldGroup>
  ),
}
