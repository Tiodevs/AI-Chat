import type { Meta, StoryObj } from "@storybook/react-vite"

import { Field, FieldError, FieldLabel } from "@/components/ui/field.tsx"
import { Textarea } from "@/components/ui/textarea.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "UI/Textarea",
  component: Textarea,
} satisfies Meta<typeof Textarea>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  render: () => (
    <div className="flex max-w-md flex-col gap-6">
      <Field>
        <FieldLabel htmlFor="question-default">
          {pt.ask.questionLabel}
        </FieldLabel>
        <Textarea id="question-default" placeholder={pt.ask.placeholder} />
      </Field>
      <Field>
        <FieldLabel htmlFor="question-focus">{pt.ask.questionLabel}</FieldLabel>
        <Textarea
          id="question-focus"
          defaultValue={pt.ask.suggestions[0].question}
          autoFocus
        />
      </Field>
      <Field data-disabled="true">
        <FieldLabel htmlFor="question-disabled">
          {pt.ask.questionLabel}
        </FieldLabel>
        <Textarea
          id="question-disabled"
          disabled
          value={pt.ask.unavailable}
          readOnly
        />
      </Field>
      <Field data-invalid="true">
        <FieldLabel htmlFor="question-invalid">
          {pt.ask.questionLabel}
        </FieldLabel>
        <Textarea
          id="question-invalid"
          aria-invalid="true"
          aria-describedby="question-error"
          defaultValue=" "
        />
        <FieldError id="question-error">{pt.couldNotContinue}</FieldError>
      </Field>
      <Field>
        <FieldLabel htmlFor="question-busy">{pt.ask.questionLabel}</FieldLabel>
        <Textarea
          id="question-busy"
          aria-busy="true"
          disabled
          value={pt.ask.sending}
          readOnly
        />
      </Field>
    </div>
  ),
}
