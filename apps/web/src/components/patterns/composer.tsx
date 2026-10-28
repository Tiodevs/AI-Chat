import { useEffect, useId, useRef } from "react"

import { Button } from "@/components/ui/button.tsx"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@/components/ui/field.tsx"
import { Spinner } from "@/components/ui/spinner.tsx"
import { Textarea } from "@/components/ui/textarea.tsx"
import { pt } from "@/i18n/pt.ts"

export function Composer({
  value,
  onChange,
  onSubmit,
  onStop,
  streaming,
  pending,
  disabled,
  disabledReason,
  error,
}: {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  onStop: () => void
  streaming: boolean
  pending: boolean
  disabled: boolean
  disabledReason: string | null
  error: string | null
}) {
  const fieldId = useId()
  const hintId = useId()
  const errorId = useId()
  const fieldRef = useRef<HTMLTextAreaElement>(null)
  const blocked = disabled || streaming

  useEffect(() => {
    const field = fieldRef.current
    if (!field) {
      return
    }
    field.style.height = "auto"
    field.style.height = `${field.scrollHeight}px`
  }, [value])

  function submit() {
    if (blocked || pending) {
      return
    }
    onSubmit()
  }

  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      <Field
        data-disabled={disabled ? true : undefined}
        data-invalid={error ? true : undefined}
      >
        <FieldLabel htmlFor={fieldId}>{pt.ask.questionLabel}</FieldLabel>
        <Textarea
          ref={fieldRef}
          id={fieldId}
          value={value}
          rows={2}
          maxLength={1000}
          placeholder={pt.ask.placeholder}
          disabled={blocked}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${hintId} ${errorId}` : hintId}
          onChange={(event) => {
            onChange(event.target.value)
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault()
              submit()
            }
          }}
        />
        <FieldDescription id={hintId}>{pt.ask.healthHint}</FieldDescription>
        {error ? <FieldError id={errorId}>{error}</FieldError> : null}
        {disabled && disabledReason ? (
          <p className="text-body text-foreground">{disabledReason}</p>
        ) : null}
      </Field>
      <div className="flex justify-end">
        {streaming ? (
          <Button
            type="button"
            className="min-h-11 md:min-h-8"
            onClick={onStop}
          >
            {pt.ask.stop}
          </Button>
        ) : (
          <Button
            type="submit"
            className="min-h-11 md:min-h-8"
            disabled={disabled || pending || value.trim() === ""}
            aria-busy={pending || undefined}
          >
            {pending ? <Spinner /> : null}
            {pending ? pt.ask.sending : pt.ask.send}
          </Button>
        )}
      </div>
    </form>
  )
}
