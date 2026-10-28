import { useState, type ReactNode } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import {
  Controller,
  useForm,
  useWatch,
  type UseFormRegisterReturn,
} from "react-hook-form"
import { Link } from "react-router"

import { PageHeading } from "@/app/page-heading.tsx"
import { ConsentFieldSet } from "@/components/patterns/consent-field-set.tsx"
import { PasswordCard } from "@/components/patterns/password-card.tsx"
import { RequestIdCopy } from "@/components/patterns/request-id-copy.tsx"
import { Button } from "@/components/ui/button.tsx"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field.tsx"
import { Input } from "@/components/ui/input.tsx"
import { Skeleton } from "@/components/ui/skeleton.tsx"
import { Spinner } from "@/components/ui/spinner.tsx"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group.tsx"
import { pt } from "@/i18n/pt.ts"
import {
  failureOffersSignIn,
  registrationFormSchema,
  visitReasons,
  visitorTypes,
  type FormValues,
} from "@/features/registration/model.ts"
import { useRegistrationForm } from "@/features/registration/useRegistrationForm.ts"

type FormModel = ReturnType<typeof useRegistrationForm>

const formFields = [
  "full_name",
  "email",
  "phone",
  "visitor_type",
  "visit_reason",
  "password",
  "accept_terms",
  "age_18_plus",
] as const

export function RegistrationFormScreen(model: FormModel) {
  return (
    <div className="mx-auto flex w-full max-w-xl flex-col gap-6">
      <PageHeading title={pt.pages.registerForm} />
      <p className="text-body text-foreground">{pt.registration.formLead}</p>
      {model.unavailable ? (
        <p role="status" className="text-body text-foreground">
          {pt.registration.unavailable}
        </p>
      ) : null}
      {model.loadError ? (
        <p role="alert" className="text-body text-danger">
          {model.loadError}
        </p>
      ) : null}
      {model.requestId ? <RequestIdCopy requestId={model.requestId} /> : null}
      {model.loading ? (
        <div className="flex flex-col gap-3" aria-hidden="true">
          <Skeleton className="h-11 w-full" />
          <Skeleton className="h-11 w-full" />
          <Skeleton className="h-11 w-2/3" />
        </div>
      ) : (
        <RegistrationForm
          defaults={model.defaults}
          documentReady={model.documentVersion !== null}
          onSubmit={model.submit}
        />
      )}
      <Button asChild variant="link" className="h-11 w-fit px-0 md:h-8">
        <Link to="/register">{pt.pages.register}</Link>
      </Button>
    </div>
  )
}

function RegistrationForm({
  defaults,
  documentReady,
  onSubmit,
}: {
  defaults: FormValues
  documentReady: boolean
  onSubmit: FormModel["submit"]
}) {
  const [pending, setPending] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [requestId, setRequestId] = useState<string | null>(null)
  const [emailTaken, setEmailTaken] = useState(false)
  const form = useForm<FormValues>({
    resolver: zodResolver(registrationFormSchema),
    defaultValues: defaults,
  })

  async function submit(values: FormValues) {
    setPending(true)
    setFormError(null)
    setRequestId(null)
    setEmailTaken(false)
    try {
      const failure = await onSubmit(values)
      if (!failure) {
        return
      }
      let known = false
      for (const [field, message] of Object.entries(failure.fieldErrors)) {
        if (isFormErrorField(field)) {
          form.setError(field, { message })
          known = true
        }
      }
      setEmailTaken(failureOffersSignIn(failure))
      setRequestId(failure.requestId)
      if (!known) {
        setFormError(failure.message)
      }
    } finally {
      setPending(false)
    }
  }

  const acceptTerms = useWatch({ control: form.control, name: "accept_terms" })
  const age = useWatch({ control: form.control, name: "age_18_plus" })
  const personalization = useWatch({
    control: form.control,
    name: "profile_personalization",
  })
  const quality = useWatch({
    control: form.control,
    name: "quality_improvement",
  })
  const visitorType = useWatch({ control: form.control, name: "visitor_type" })
  const visitReason = useWatch({ control: form.control, name: "visit_reason" })
  const consents = {
    accept_terms: acceptTerms,
    age_18_plus: age,
    profile_personalization: personalization,
    quality_improvement: quality,
  }
  const emailError = form.formState.errors.email?.message

  return (
    <form
      aria-labelledby="page-title"
      className="flex flex-col gap-6"
      noValidate
      onSubmit={(event) => {
        void form.handleSubmit(submit)(event)
      }}
    >
      <FieldGroup>
        <TextField
          id="full_name"
          label={pt.registration.fields.full_name}
          type="text"
          autoComplete="name"
          pending={pending}
          error={form.formState.errors.full_name?.message}
          registration={form.register("full_name")}
        />
        <TextField
          id="email"
          label={pt.registration.fields.email}
          type="email"
          autoComplete="email"
          pending={pending}
          error={emailError}
          registration={form.register("email")}
          extra={
            emailTaken ? (
              <Link
                to="/sign-in"
                className="w-fit text-body text-foreground underline"
              >
                {pt.registration.signIn}
              </Link>
            ) : null
          }
        />
        <TextField
          id="phone"
          label={pt.registration.fields.phone}
          type="tel"
          autoComplete="tel"
          pending={pending}
          error={form.formState.errors.phone?.message}
          registration={form.register("phone")}
          description={pt.registration.optionalHint}
        />
        <ChoiceField
          label={pt.registration.fields.visitor_type}
          value={visitorType}
          options={visitorTypes}
          labels={pt.registration.visitorTypes}
          error={form.formState.errors.visitor_type?.message}
          onChange={(value) => form.setValue("visitor_type", value)}
        />
        <ChoiceField
          label={pt.registration.fields.visit_reason}
          value={visitReason}
          options={visitReasons}
          labels={pt.registration.visitReasons}
          error={form.formState.errors.visit_reason?.message}
          onChange={(value) => form.setValue("visit_reason", value)}
        />
        <p className="text-body text-foreground">
          {pt.registration.sensitiveKept}
        </p>
        <Controller
          name="password"
          control={form.control}
          render={({ field, fieldState }) => (
            <PasswordCard
              value={field.value}
              onChange={field.onChange}
              pending={pending}
              error={fieldState.error?.message ?? null}
              moveFocus={false}
            />
          )}
        />
      </FieldGroup>
      <ConsentFieldSet
        value={consents}
        disabled={pending}
        errors={{
          accept_terms: form.formState.errors.accept_terms?.message,
          age_18_plus: form.formState.errors.age_18_plus?.message,
        }}
        onChange={(next) => {
          form.setValue("accept_terms", next.accept_terms, {
            shouldValidate: form.formState.isSubmitted,
          })
          form.setValue("age_18_plus", next.age_18_plus, {
            shouldValidate: form.formState.isSubmitted,
          })
          form.setValue("profile_personalization", next.profile_personalization)
          form.setValue("quality_improvement", next.quality_improvement)
        }}
      />
      {formError ? (
        <p role="alert" className="text-body text-danger">
          {formError}
        </p>
      ) : null}
      {requestId ? <RequestIdCopy requestId={requestId} /> : null}
      <Button
        type="submit"
        className="min-h-11 md:min-h-8"
        disabled={pending || !documentReady}
      >
        {pending ? <Spinner aria-hidden data-icon="inline-start" /> : null}
        {pending ? pt.registration.creating : pt.registration.createAccount}
      </Button>
    </form>
  )
}

function TextField({
  id,
  label,
  type,
  autoComplete,
  pending,
  error,
  registration,
  description,
  extra,
}: {
  id: string
  label: string
  type: string
  autoComplete: string
  pending: boolean
  error?: string
  registration: UseFormRegisterReturn
  description?: string
  extra?: ReactNode
}) {
  const errorId = `${id}-error`
  return (
    <Field
      data-invalid={error ? true : undefined}
      data-disabled={pending || undefined}
    >
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Input
        id={id}
        type={type}
        autoComplete={autoComplete}
        disabled={pending}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        className="h-11 md:h-8"
        {...registration}
      />
      {description ? <FieldDescription>{description}</FieldDescription> : null}
      {error ? <FieldError id={errorId}>{error}</FieldError> : null}
      {extra}
    </Field>
  )
}

function ChoiceField<T extends string>({
  label,
  value,
  options,
  labels,
  error,
  onChange,
}: {
  label: string
  value: string
  options: readonly T[]
  labels: Record<T, string>
  error?: string
  onChange: (value: string) => void
}) {
  return (
    <Field data-invalid={error ? true : undefined}>
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
      {error ? <FieldError>{error}</FieldError> : null}
    </Field>
  )
}

function isFormErrorField(field: string): field is (typeof formFields)[number] {
  return formFields.some((item) => item === field)
}
