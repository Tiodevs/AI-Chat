import { z } from "zod"

import { pt } from "@/i18n/pt.ts"

export {
  failureFrom,
  visitReasons,
  visitorTypes,
  type SubmitFailure,
} from "@/features/registration/model.ts"

export type ConsentState = {
  purpose: string
  granted: boolean
  document_version: string | null
  granted_at: string | null
}

export type Consents = {
  current: ConsentState[]
  history: {
    purpose: string
    document_version: string
    granted_at: string
    revoked_at: string | null
    source: string
  }[]
}

export const termsPurpose = "terms_and_privacy_notice"
export const personalizationPurpose = "profile_personalization"
export const qualityPurpose = "quality_improvement"

export type OptionalPurpose =
  | typeof personalizationPurpose
  | typeof qualityPurpose

const phonePattern = /^[0-9+\-() ]+$/

export const profileSchema = z.object({
  full_name: z
    .string()
    .trim()
    .min(1, pt.account.profile.nameRequired)
    .min(2, pt.account.profile.nameInvalid)
    .max(80, pt.account.profile.nameInvalid),
  phone: z
    .string()
    .trim()
    .refine(
      (value) =>
        value === "" ||
        (value.length >= 7 && value.length <= 20 && phonePattern.test(value)),
      pt.account.profile.phoneInvalid,
    ),
  visitor_type: z.string(),
  visit_reason: z.string(),
})

export type ProfileValues = z.infer<typeof profileSchema>

export type ProfileSource = {
  full_name: string
  phone: string | null
  visitor_type: string | null
  visit_reason: string | null
}

export function profileDefaults(me: ProfileSource): ProfileValues {
  return {
    full_name: me.full_name,
    phone: me.phone ?? "",
    visitor_type: me.visitor_type ?? "",
    visit_reason: me.visit_reason ?? "",
  }
}

/** Só os campos sensíveis seguem no pedido quando a personalização está ativa. */
export function profilePatch(values: ProfileValues, personalization: boolean) {
  const body: {
    full_name: string
    phone: string | null
    visitor_type?: string | null
    visit_reason?: string | null
  } = {
    full_name: values.full_name.trim(),
    phone: values.phone.trim() === "" ? null : values.phone.trim(),
  }
  if (personalization) {
    body.visitor_type = values.visitor_type === "" ? null : values.visitor_type
    body.visit_reason = values.visit_reason === "" ? null : values.visit_reason
  }
  return body
}

export function consentFor(
  consents: Consents | undefined,
  purpose: string,
): ConsentState | null {
  return consents?.current.find((item) => item.purpose === purpose) ?? null
}

export function isGranted(consents: Consents | undefined, purpose: string) {
  return consentFor(consents, purpose)?.granted === true
}

/** A exclusão só vale com a palavra exata, sem espaços nas pontas. */
export function deleteConfirmed(text: string) {
  return text.trim() === pt.account.privacy.deleteConfirmWord
}

export function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  })
}

export function grantedOn(iso: string | null | undefined) {
  if (!iso) {
    return pt.account.privacy.off
  }
  return pt.account.privacy.grantedOn.replace("{date}", formatDate(iso))
}
