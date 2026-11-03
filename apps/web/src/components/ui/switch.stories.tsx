import type { Meta, StoryObj } from "@storybook/react-vite"

import { Field, FieldError, FieldLabel } from "@/components/ui/field.tsx"
import { Switch } from "@/components/ui/switch.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "UI/Switch",
  component: Switch,
} satisfies Meta<typeof Switch>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  render: () => (
    <div className="flex w-96 flex-col gap-4">
      <Field orientation="horizontal">
        <Switch id="switch-off" />
        <FieldLabel htmlFor="switch-off">{pt.registration.quality}</FieldLabel>
      </Field>
      <Field orientation="horizontal">
        <Switch id="switch-on" defaultChecked />
        <FieldLabel htmlFor="switch-on">{pt.registration.quality}</FieldLabel>
      </Field>
      <Field orientation="horizontal">
        <Switch id="switch-focus" autoFocus />
        <FieldLabel htmlFor="switch-focus">{pt.registration.quality}</FieldLabel>
      </Field>
      <Field orientation="horizontal" data-disabled>
        <Switch id="switch-disabled" disabled />
        <FieldLabel htmlFor="switch-disabled">
          {pt.registration.quality}
        </FieldLabel>
      </Field>
      <Field orientation="horizontal" data-invalid>
        <Switch id="switch-invalid" aria-invalid />
        <FieldLabel htmlFor="switch-invalid">
          {pt.registration.quality}
        </FieldLabel>
        <FieldError>{pt.couldNotContinue}</FieldError>
      </Field>
    </div>
  ),
}
