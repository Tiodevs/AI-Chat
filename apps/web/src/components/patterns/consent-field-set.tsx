import { useId, type ReactNode } from "react"
import { Link } from "react-router"

import { Checkbox } from "@/components/ui/checkbox.tsx"
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field.tsx"
import { Label } from "@/components/ui/label.tsx"
import { pt } from "@/i18n/pt.ts"
import { type Consents } from "@/features/registration/model.ts"

export function ConsentFieldSet({
  value,
  onChange,
  errors,
  disabled,
}: {
  value: Consents
  onChange: (value: Consents) => void
  errors: Partial<Record<"accept_terms" | "age_18_plus", string>>
  disabled: boolean
}) {
  function update(patch: Partial<Consents>) {
    onChange({ ...value, ...patch })
  }

  return (
    <FieldSet disabled={disabled} className="gap-5">
      <FieldLegend>{pt.registration.consentsTitle}</FieldLegend>
      <FieldGroup>
        <p className="text-label text-muted-foreground">
          {pt.registration.requiredLegend}
        </p>
        <ConsentCheck
          checked={value.accept_terms}
          disabled={disabled}
          label={pt.registration.terms}
          error={errors.accept_terms}
          onCheckedChange={(checked) => update({ accept_terms: checked })}
          description={
            <span className="flex flex-wrap gap-3">
              <Link to="/terms" className="underline underline-offset-4">
                {pt.registration.termsLink}
              </Link>
              <Link to="/privacy" className="underline underline-offset-4">
                {pt.registration.privacyLink}
              </Link>
            </span>
          }
        />
        <ConsentCheck
          checked={value.age_18_plus}
          disabled={disabled}
          label={pt.registration.age}
          error={errors.age_18_plus}
          onCheckedChange={(checked) => update({ age_18_plus: checked })}
        />
        <p className="text-label text-muted-foreground">
          {pt.registration.optionalLegend}
        </p>
        <div
          data-highlighted="personalization"
          className="flex flex-col gap-2 rounded-2xl border border-warning bg-[color-mix(in_oklab,var(--warning)_15%,transparent)] p-4"
        >
          <p className="text-label text-foreground">
            {pt.registration.personalizationBadge}
          </p>
          <ConsentCheck
            checked={value.profile_personalization}
            disabled={disabled}
            label={pt.registration.personalization}
            onCheckedChange={(checked) =>
              update({ profile_personalization: checked })
            }
            description={pt.registration.personalizationNote}
          />
        </div>
        <ConsentCheck
          checked={value.quality_improvement}
          disabled={disabled}
          label={pt.registration.quality}
          onCheckedChange={(checked) =>
            update({ quality_improvement: checked })
          }
          description={pt.registration.qualityNote}
        />
      </FieldGroup>
    </FieldSet>
  )
}

function ConsentCheck({
  checked,
  disabled,
  label,
  error,
  description,
  onCheckedChange,
}: {
  checked: boolean
  disabled: boolean
  label: string
  error?: string
  description?: ReactNode
  onCheckedChange: (checked: boolean) => void
}) {
  const id = useId()
  const errorId = useId()
  const descriptionId = useId()
  const describedBy = [
    description ? descriptionId : null,
    error ? errorId : null,
  ]
    .filter(Boolean)
    .join(" ")

  return (
    <Field
      orientation="horizontal"
      data-invalid={error ? true : undefined}
      data-disabled={disabled || undefined}
    >
      <Checkbox
        id={id}
        checked={checked}
        disabled={disabled}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy || undefined}
        onCheckedChange={(next) => onCheckedChange(next === true)}
      />
      <FieldContent>
        <Label htmlFor={id}>{label}</Label>
        {description ? (
          <FieldDescription id={descriptionId}>{description}</FieldDescription>
        ) : null}
        {error ? <FieldError id={errorId}>{error}</FieldError> : null}
      </FieldContent>
    </Field>
  )
}
