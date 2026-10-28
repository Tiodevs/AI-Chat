import { useId, useRef } from "react"

import { Button } from "@/components/ui/button.tsx"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@/components/ui/field.tsx"
import { Input } from "@/components/ui/input.tsx"
import { Spinner } from "@/components/ui/spinner.tsx"
import { pt } from "@/i18n/pt.ts"
import { useGSAP } from "@/motion/gsap.ts"
import { useMotion } from "@/motion/MotionProvider.tsx"
import { presets } from "@/motion/presets.ts"
import { passwordStrength } from "@/features/registration/model.ts"

export function PasswordCard({
  value,
  onChange,
  onSubmit,
  pending,
  error,
  moveFocus,
}: {
  value: string
  onChange: (value: string) => void
  onSubmit?: () => void
  pending: boolean
  error: string | null
  moveFocus: boolean
}) {
  const rootRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const fieldId = useId()
  const errorId = useId()
  const meterId = useId()
  const { reduced } = useMotion()
  const strength = passwordStrength(value)
  const strengthText = pt.registration.strength[strength.level]

  useGSAP(
    () => {
      presets.enterPassword(rootRef.current, reduced, () => {
        if (moveFocus) {
          inputRef.current?.focus()
        }
      })
    },
    { scope: rootRef, dependencies: [reduced, moveFocus] }
  )

  const body = (
    <>
      <Field
        data-invalid={error ? true : undefined}
        data-disabled={pending || undefined}
      >
        <FieldLabel htmlFor={fieldId}>
          {pt.registration.fields.password}
        </FieldLabel>
        <Input
          ref={inputRef}
          id={fieldId}
          type="password"
          autoComplete="new-password"
          value={value}
          disabled={pending}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${meterId} ${errorId}` : meterId}
          className="h-11 md:h-8"
          onChange={(event) => onChange(event.target.value)}
        />
        <FieldDescription id={meterId}>
          {pt.registration.passwordHint}
        </FieldDescription>
        <StrengthMeter score={strength.score} text={strengthText} />
        {error ? <FieldError id={errorId}>{error}</FieldError> : null}
      </Field>
      <p className="text-body text-foreground">
        {pt.registration.passwordNote}
      </p>
      {onSubmit ? (
        <Button
          type="submit"
          className="min-h-11 md:min-h-8"
          disabled={pending || value === ""}
        >
          {pending ? <Spinner aria-hidden data-icon="inline-start" /> : null}
          {pending ? pt.registration.sending : pt.registration.send}
        </Button>
      ) : null}
    </>
  )

  const fields = onSubmit ? (
    <form
      aria-label={pt.registration.passwordForm}
      className="flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit()
      }}
    >
      {body}
    </form>
  ) : (
    <div className="flex flex-col gap-4">{body}</div>
  )

  return (
    <div ref={rootRef} className="rounded-card bg-card p-4 md:p-5">
      {fields}
    </div>
  )
}

function StrengthMeter({ score, text }: { score: number; text: string }) {
  return (
    <div className="flex flex-col gap-2">
      <div
        role="meter"
        aria-label={pt.registration.strengthLabel}
        aria-valuemin={0}
        aria-valuemax={4}
        aria-valuenow={score}
        aria-valuetext={text}
        className="h-1 overflow-hidden rounded-full bg-muted"
      >
        <div
          aria-hidden="true"
          className="h-full w-full origin-left bg-foreground"
          style={{ transform: `scaleX(${score / 4})` }}
        />
      </div>
      <p className="text-caption text-foreground">{text}</p>
    </div>
  )
}
