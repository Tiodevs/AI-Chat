import { z } from "zod"

import { pt } from "@/i18n/pt.ts"

export {
  failureFrom,
  type SubmitFailure,
} from "@/features/registration/model.ts"

export const requestTypes = [
  "access",
  "correction",
  "deletion",
  "portability",
  "consent_revocation",
  "information_about_sharing",
  "objection",
  "other",
] as const

export type RequestType = (typeof requestTypes)[number]

export const noticeSections = [
  { id: "quem-cuida", key: "controller" },
  { id: "dados", key: "data" },
  { id: "saude", key: "health" },
  { id: "compartilhamento", key: "processors" },
  { id: "retencao", key: "retention" },
  { id: "direitos", key: "rights" },
  { id: "cookies", key: "cookies" },
  { id: "seguranca", key: "security" },
  { id: "incidentes", key: "incidents" },
  { id: "pedidos", key: "channel" },
] as const

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export const requestSchema = z.object({
  contact_email: z
    .string()
    .trim()
    .regex(emailPattern, pt.privacyRequest.emailInvalid),
  request_type: z
    .string()
    .refine(
      (value) => requestTypes.some((item) => item === value),
      pt.privacyRequest.typeRequired,
    ),
  description: z
    .string()
    .trim()
    .min(1, pt.privacyRequest.descriptionRequired)
    .max(2000, pt.privacyRequest.descriptionTooLong),
})

export type RequestValues = z.infer<typeof requestSchema>

export function emptyRequest(email: string | null | undefined): RequestValues {
  return { contact_email: email ?? "", request_type: "", description: "" }
}

export function sentMessage(dueAt: string) {
  const date = new Date(dueAt).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  })
  return pt.privacyRequest.sent.replace("{date}", date)
}
