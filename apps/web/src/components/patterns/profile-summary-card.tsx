import { useEffect, useId, useRef, useState } from "react"
import { CheckIcon, CircleAlert } from "lucide-react"
import { Link } from "react-router"

import { Button } from "@/components/ui/button.tsx"
import { Field, FieldLabel } from "@/components/ui/field.tsx"
import { Input } from "@/components/ui/input.tsx"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group.tsx"
import { pt } from "@/i18n/pt.ts"
import { useGSAP } from "@/motion/gsap.ts"
import { useMotion } from "@/motion/MotionProvider.tsx"
import { presets } from "@/motion/presets.ts"
import {
  changedFieldAnnouncement,
  displayFieldValue,
  emailOffersSignIn,
  fieldLabel,
  fieldNames,
  visitReasons,
  visitorTypes,
  type FieldName,
  type RegistrationFields,
} from "@/features/registration/model.ts"

export function ProfileSummaryCard({
  fields,
  fieldErrors,
  pending,
  onEdit,
  signInHref = "/sign-in",
}: {
  fields: RegistrationFields
  fieldErrors: Record<string, string>
  pending: boolean
  onEdit: (field: FieldName, value: string | null) => Promise<boolean>
  signInHref?: string
}) {
  const titleId = useId()
  const previous = useRef(fields)
  const [announcement, setAnnouncement] = useState("")

  useEffect(() => {
    const text = changedFieldAnnouncement(previous.current, fields)
    previous.current = fields
    if (text) {
      setAnnouncement(text)
    }
  }, [fields])

  return (
    <section
      aria-labelledby={titleId}
      className="flex flex-col gap-4 rounded-card bg-card p-4 md:p-5"
    >
      <h2 id={titleId} className="text-label text-foreground">
        {pt.registration.summaryTitle}
      </h2>
      <div className="sr-only" role="status" aria-live="polite">
        {announcement}
      </div>
      <ul className="m-0 flex list-none flex-col gap-4 p-0">
        {fieldNames.map((name) => (
          <SummaryField
            key={name}
            name={name}
            value={fields[name]}
            error={fieldErrors[name] ?? null}
            pending={pending}
            signInHref={signInHref}
            onEdit={onEdit}
          />
        ))}
      </ul>
    </section>
  )
}

function SummaryField({
  name,
  value,
  error,
  pending,
  signInHref,
  onEdit,
}: {
  name: FieldName
  value: string | null
  error: string | null
  pending: boolean
  signInHref: string
  onEdit: (field: FieldName, value: string | null) => Promise<boolean>
}) {
  const rootRef = useRef<HTMLLIElement>(null)
  const reasonId = useId()
  const { reduced } = useMotion()
  const [openReason, setOpenReason] = useState(false)
  const [editing, setEditing] = useState(false)
  const label = fieldLabel(name)
  const shown = displayFieldValue(name, value)
  const offerSignIn = name === "email" && emailOffersSignIn(error ?? undefined)

  useGSAP(
    () => {
      if (!value) {
        return
      }
      presets.confirmField(rootRef.current, reduced)
    },
    { scope: rootRef, dependencies: [value, reduced] }
  )

  return (
    <li ref={rootRef} className="relative flex flex-col gap-2">
      <div
        data-highlight
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 rounded-lg bg-[color-mix(in_oklab,var(--success)_15%,transparent)] opacity-0"
      />
      <div className="relative flex flex-col gap-2">
        <div className="flex items-start justify-between gap-3">
          <p className="text-label text-muted-foreground">{label}</p>
          {shown ? (
            <CheckIcon
              data-confirm
              aria-hidden="true"
              className="size-4 text-success"
            />
          ) : null}
        </div>
        {editing ? (
          <FieldEditor
            name={name}
            label={label}
            value={value}
            pending={pending}
            onCancel={() => setEditing(false)}
            onSave={async (next) => {
              const saved = await onEdit(name, next)
              if (saved) {
                setEditing(false)
              }
            }}
          />
        ) : (
          <div className="flex items-start justify-between gap-3">
            <p className="text-body text-foreground">
              {shown ?? pt.registration.summaryEmpty}
            </p>
            <Button
              type="button"
              variant="ghost"
              className="min-h-11 shrink-0 md:min-h-8"
              disabled={pending}
              onClick={() => setEditing(true)}
            >
              {pt.registration.edit}
              <span className="sr-only"> {label}</span>
            </Button>
          </div>
        )}
        <a
          href={`#${reasonId}`}
          className="w-fit text-body text-foreground underline underline-offset-4"
          aria-expanded={openReason}
          onClick={(event) => {
            event.preventDefault()
            setOpenReason((current) => !current)
          }}
        >
          {pt.registration.why}
          <span className="sr-only"> {label}</span>
        </a>
        <p
          id={reasonId}
          hidden={openReason ? undefined : true}
          className="text-body text-foreground"
        >
          {pt.registration.reasons[name]}
        </p>
        {error ? (
          <div
            role="alert"
            className="flex items-start gap-2 text-body text-danger"
          >
            <CircleAlert
              className="mt-0.5 size-4 shrink-0"
              aria-hidden="true"
            />
            <p>{error}</p>
          </div>
        ) : null}
        {offerSignIn ? (
          <Link
            to={signInHref}
            className="w-fit text-body text-foreground underline underline-offset-4"
          >
            {pt.registration.signIn}
          </Link>
        ) : null}
      </div>
    </li>
  )
}

function FieldEditor({
  name,
  label,
  value,
  pending,
  onSave,
  onCancel,
}: {
  name: FieldName
  label: string
  value: string | null
  pending: boolean
  onSave: (value: string | null) => Promise<void>
  onCancel: () => void
}) {
  const inputId = useId()
  const [draft, setDraft] = useState(value ?? "")

  return (
    <form
      aria-label={label}
      className="flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault()
        void onSave(draft.trim() ? draft.trim() : null)
      }}
    >
      {name === "visitor_type" || name === "visit_reason" ? (
        <ChoiceEditor
          name={name}
          label={label}
          value={draft}
          onChange={setDraft}
        />
      ) : (
        <Field data-disabled={pending || undefined}>
          <FieldLabel htmlFor={inputId}>{label}</FieldLabel>
          <Input
            id={inputId}
            value={draft}
            disabled={pending}
            autoComplete={autoCompleteFor(name)}
            type={
              name === "email" ? "email" : name === "phone" ? "tel" : "text"
            }
            className="h-11 md:h-8"
            onChange={(event) => setDraft(event.target.value)}
          />
        </Field>
      )}
      <div className="flex flex-wrap gap-2">
        <Button
          type="submit"
          className="min-h-11 md:min-h-8"
          disabled={pending}
        >
          {pt.registration.save}
        </Button>
        <Button
          type="button"
          variant="outline"
          className="min-h-11 md:min-h-8"
          disabled={pending}
          onClick={onCancel}
        >
          {pt.registration.cancel}
        </Button>
      </div>
    </form>
  )
}

function ChoiceEditor({
  name,
  label,
  value,
  onChange,
}: {
  name: "visitor_type" | "visit_reason"
  label: string
  value: string
  onChange: (value: string) => void
}) {
  if (name === "visitor_type") {
    return (
      <ChoiceGroup
        label={label}
        value={value}
        options={visitorTypes}
        labels={pt.registration.visitorTypes}
        onChange={onChange}
      />
    )
  }
  return (
    <ChoiceGroup
      label={label}
      value={value}
      options={visitReasons}
      labels={pt.registration.visitReasons}
      onChange={onChange}
    />
  )
}

function ChoiceGroup<T extends string>({
  label,
  value,
  options,
  labels,
  onChange,
}: {
  label: string
  value: string
  options: readonly T[]
  labels: Record<T, string>
  onChange: (value: string) => void
}) {
  return (
    <Field>
      <p className="text-label text-foreground">{label}</p>
      <ToggleGroup
        type="single"
        value={value}
        aria-label={label}
        onValueChange={onChange}
      >
        {options.map((option) => (
          <ToggleGroupItem key={option} value={option}>
            {labels[option]}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </Field>
  )
}

function autoCompleteFor(name: FieldName) {
  if (name === "full_name") {
    return "name"
  }
  if (name === "email") {
    return "email"
  }
  if (name === "phone") {
    return "tel"
  }
  return "off"
}
