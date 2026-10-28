import type { Meta, StoryObj } from "@storybook/react-vite"

import { Checkbox } from "@/components/ui/checkbox.tsx"
import { Field, FieldError, FieldLabel } from "@/components/ui/field.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "UI/Checkbox",
  component: Checkbox,
} satisfies Meta<typeof Checkbox>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  render: () => (
    <div className="flex w-80 flex-col gap-4">
      <Field orientation="horizontal">
        <Checkbox id="check-rest" />
        <FieldLabel htmlFor="check-rest">{pt.registration.age}</FieldLabel>
      </Field>
      <Field orientation="horizontal">
        <Checkbox id="check-on" defaultChecked />
        <FieldLabel htmlFor="check-on">{pt.registration.age}</FieldLabel>
      </Field>
      <Field orientation="horizontal">
        <Checkbox id="check-focus" autoFocus />
        <FieldLabel htmlFor="check-focus">{pt.registration.age}</FieldLabel>
      </Field>
      <Field orientation="horizontal" data-disabled>
        <Checkbox id="check-disabled" disabled />
        <FieldLabel htmlFor="check-disabled">{pt.registration.age}</FieldLabel>
      </Field>
      <Field orientation="horizontal" data-invalid>
        <Checkbox
          id="check-invalid"
          aria-invalid="true"
          aria-describedby="check-invalid-error"
        />
        <FieldLabel htmlFor="check-invalid">{pt.registration.terms}</FieldLabel>
        <FieldError id="check-invalid-error">
          {pt.registration.termsRequired}
        </FieldError>
      </Field>
      <Field orientation="horizontal" data-disabled>
        <Checkbox id="check-busy" disabled aria-busy="true" />
        <FieldLabel htmlFor="check-busy">{pt.loading}</FieldLabel>
      </Field>
    </div>
  ),
}
