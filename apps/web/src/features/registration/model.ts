import { z } from "zod"

import {
  fieldErrorsFrom,
  messageFrom,
  requestIdFrom,
  retryAfterFrom,
} from "@/features/auth/api-error.ts"
import { pt } from "@/i18n/pt.ts"

export const registrationPhases = [
  "details",
  "password",
  "review",
  "agree",
] as const

export type RegistrationPhase = (typeof registrationPhases)[number]

export const fieldNames = [
  "full_name",
  "email",
  "phone",
  "visitor_type",
  "visit_reason",
] as const

export type FieldName = (typeof fieldNames)[number]

export const visitorTypes = ["patient", "visitor", "caregiver"] as const

export type VisitorType = (typeof visitorTypes)[number]

export const visitReasons = [
  "visiting_someone",
  "own_appointment",
  "exam_or_test",
  "accompanying_someone",
  "administrative",
  "other",
] as const

export type VisitReason = (typeof visitReasons)[number]

const optionalSteps = ["phone", "visitor_type", "visit_reason"] as const

export type RegistrationFields = {
  full_name: string | null
  email: string | null
  phone: string | null
  visitor_type: string | null
  visit_reason: string | null
}

export type TranscriptMessage = {
  role: "user" | "assistant"
  text: string
  created_at: string
}

export type RegistrationSession = {
  id: string
  status: string
  path: "chat" | "form"
  fields: RegistrationFields
  field_errors: Record<string, string>
  next_step: string
  prompt: string
  messages: TranscriptMessage[]
  expires_at: string
}

export type Consents = {
  accept_terms: boolean
  age_18_plus: boolean
  profile_personalization: boolean
  quality_improvement: boolean
}

export type FormValues = Consents & {
  full_name: string
  email: string
  phone: string
  visitor_type: string
  visit_reason: string
  password: string
}

export type PasswordStrength =
  "empty" | "short" | "long" | "fair" | "good" | "strong"

export type SubmitFailure = {
  ok: false
  status: number
  message: string
  fieldErrors: Record<string, string>
  requestId: string | null
}

const sessionIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

const phonePattern = /^[0-9+\-() ]{7,20}$/

const takenPhrase = "já tem uma conta"

export function sessionIdFrom(value: string | null) {
  if (!value || !sessionIdPattern.test(value)) {
    return null
  }
  return value
}

export function unavailableFrom(value: string | null) {
  return value === "1"
}

export function canSkipStep(step: string) {
  return optionalSteps.some((item) => item === step)
}

export function phaseForStep(step: string): RegistrationPhase {
  if (step === "password") {
    return "password"
  }
  if (step === "review") {
    return "review"
  }
  if (step === "acceptance") {
    return "agree"
  }
  return "details"
}

export function phaseScale(phase: RegistrationPhase) {
  const index = registrationPhases.indexOf(phase)
  return (index + 1) / registrationPhases.length
}

export function emptyFields(): RegistrationFields {
  return {
    full_name: null,
    email: null,
    phone: null,
    visitor_type: null,
    visit_reason: null,
  }
}

export function filledFieldCount(fields: RegistrationFields) {
  return fieldNames.filter((name) => fields[name]).length
}

export function fieldLabel(name: FieldName) {
  return pt.registration.fields[name]
}

export function displayFieldValue(name: FieldName, value: string | null) {
  if (!value) {
    return null
  }
  if (name === "visitor_type" && isVisitorType(value)) {
    return pt.registration.visitorTypes[value]
  }
  if (name === "visit_reason" && isVisitReason(value)) {
    return pt.registration.visitReasons[value]
  }
  return value
}

export function changedFieldAnnouncement(
  previous: RegistrationFields | null,
  next: RegistrationFields
) {
  return fieldNames
    .filter((name) => previous?.[name] !== next[name] && next[name])
    .map((name) =>
      pt.registration.understood
        .replace("{field}", fieldLabel(name))
        .replace("{value}", displayFieldValue(name, next[name]) ?? "")
    )
    .join(". ")
}

export function emailOffersSignIn(message: string | undefined) {
  return Boolean(message?.includes(takenPhrase))
}

export function failureOffersSignIn(failure: SubmitFailure) {
  return failure.status === 409 || emailOffersSignIn(failure.fieldErrors.email)
}

export function passwordStrength(password: string): {
  level: PasswordStrength
  score: number
} {
  if (!password) {
    return { level: "empty", score: 0 }
  }
  if (password.length < 12) {
    return { level: "short", score: 1 }
  }
  if (password.length > 72) {
    return { level: "long", score: 1 }
  }
  let classes = 0
  if (/[a-z]/.test(password)) {
    classes += 1
  }
  if (/[A-Z]/.test(password)) {
    classes += 1
  }
  if (/[0-9]/.test(password)) {
    classes += 1
  }
  if (/[^A-Za-z0-9]/.test(password)) {
    classes += 1
  }
  if (classes >= 3) {
    return { level: "strong", score: 4 }
  }
  if (classes === 2) {
    return { level: "good", score: 3 }
  }
  return { level: "fair", score: 2 }
}

export function emptyConsents(): Consents {
  return {
    accept_terms: false,
    age_18_plus: false,
    profile_personalization: false,
    quality_improvement: false,
  }
}

export function consentIssues(value: Consents) {
  const issues: Partial<Record<"accept_terms" | "age_18_plus", string>> = {}
  if (!value.accept_terms) {
    issues.accept_terms = pt.registration.termsRequired
  }
  if (!value.age_18_plus) {
    issues.age_18_plus = pt.registration.ageRequired
  }
  return issues
}

export function emptyFormValues(): FormValues {
  return {
    full_name: "",
    email: "",
    phone: "",
    visitor_type: "",
    visit_reason: "",
    password: "",
    ...emptyConsents(),
  }
}

export function formValuesFromFields(
  fields: RegistrationFields | null
): FormValues {
  return {
    ...emptyFormValues(),
    full_name: fields?.full_name ?? "",
    email: fields?.email ?? "",
    phone: fields?.phone ?? "",
    visitor_type: fields?.visitor_type ?? "",
    visit_reason: fields?.visit_reason ?? "",
    password: "",
  }
}

export function registrationLimitMessage(seconds: number) {
  const minutes = Math.max(1, Math.ceil(seconds / 60))
  if (minutes === 1) {
    return pt.registration.limitedOne
  }
  return pt.registration.limitedMany.replace("{minutes}", String(minutes))
}

export function failureFrom(error: unknown, status: number): SubmitFailure {
  const retry = status === 429 ? retryAfterFrom(error) : null
  return {
    ok: false,
    status,
    message:
      retry == null
        ? messageFrom(error, pt.couldNotContinue)
        : registrationLimitMessage(retry),
    fieldErrors: fieldErrorsFrom(error),
    requestId: requestIdFrom(error),
  }
}

export function formPath(sessionId: string | null, unavailable = false) {
  const params = new URLSearchParams()
  if (sessionId) {
    params.set("session", sessionId)
  }
  if (unavailable) {
    params.set("unavailable", "1")
  }
  const query = params.toString()
  return query ? `/register/form?${query}` : "/register/form"
}

function emptyToNull(value: string) {
  const trimmed = value.trim()
  return trimmed ? trimmed : null
}

export function toFormPayload(
  values: FormValues,
  documentVersion: string,
  sessionId: string | null
) {
  return {
    session_id: sessionId,
    full_name: values.full_name.trim(),
    email: values.email.trim(),
    phone: emptyToNull(values.phone),
    visitor_type: emptyToNull(values.visitor_type),
    visit_reason: emptyToNull(values.visit_reason),
    password: values.password,
    accept_terms: values.accept_terms,
    document_version: documentVersion,
    age_18_plus: values.age_18_plus,
    profile_personalization: values.profile_personalization,
    quality_improvement: values.quality_improvement,
  }
}

function issue(message: string) {
  return { code: "custom" as const, message }
}

export const registrationFormSchema = z
  .object({
    full_name: z
      .string()
      .trim()
      .superRefine((value, context) => {
        if (!value) {
          context.addIssue(issue(pt.registration.nameRequired))
          return
        }
        if (value.length < 2 || value.length > 80) {
          context.addIssue(issue(pt.registration.nameInvalid))
        }
      }),
    email: z
      .string()
      .trim()
      .superRefine((value, context) => {
        if (!value) {
          context.addIssue(issue(pt.registration.emailRequired))
          return
        }
        if (!z.email().safeParse(value).success) {
          context.addIssue(issue(pt.registration.emailInvalid))
        }
      }),
    phone: z
      .string()
      .trim()
      .superRefine((value, context) => {
        if (value && !phonePattern.test(value)) {
          context.addIssue(issue(pt.registration.phoneInvalid))
        }
      }),
    visitor_type: z.string().superRefine((value, context) => {
      if (value && !isVisitorType(value)) {
        context.addIssue(issue(pt.registration.visitorInvalid))
      }
    }),
    visit_reason: z.string().superRefine((value, context) => {
      if (value && !isVisitReason(value)) {
        context.addIssue(issue(pt.registration.reasonInvalid))
      }
    }),
    password: z.string().superRefine((value, context) => {
      if (!value) {
        context.addIssue(issue(pt.registration.passwordRequired))
        return
      }
      if (value.length < 12 || value.length > 72) {
        context.addIssue(issue(pt.registration.passwordInvalid))
      }
    }),
    accept_terms: z.boolean(),
    age_18_plus: z.boolean(),
    profile_personalization: z.boolean(),
    quality_improvement: z.boolean(),
  })
  .superRefine((value, context) => {
    if (!value.accept_terms) {
      context.addIssue({
        ...issue(pt.registration.termsRequired),
        path: ["accept_terms"],
      })
    }
    if (!value.age_18_plus) {
      context.addIssue({
        ...issue(pt.registration.ageRequired),
        path: ["age_18_plus"],
      })
    }
  })

export function isVisitorType(value: string): value is VisitorType {
  return visitorTypes.some((item) => item === value)
}

export function isVisitReason(value: string): value is VisitReason {
  return visitReasons.some((item) => item === value)
}

export function isFieldName(value: string): value is FieldName {
  return fieldNames.some((item) => item === value)
}
