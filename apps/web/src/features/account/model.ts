/**
 * Modelo da conta do membro: tipos dos consentimentos, regras do formulário
 * de perfil e formatação de datas. Só funções puras, sem React e sem rede.
 *
 * Quem usa: `useAccount.ts`, `useLegalAccept.ts` e `account-screen.tsx`.
 * Usa o `pt` de `i18n/pt.ts` e reaproveita do cadastro
 * (`features/registration/model.ts`) o mapa de erros da API e as listas
 * fechadas de tipo de visitante e de motivo da visita.
 *
 * SDD 8.5 (regras dos campos), 11.5 (direitos do titular), 12 (`/v1/me` e
 * `/v1/me/consents`) e 15.5 (Conta).
 */
import { z } from "zod"

import { pt } from "@/i18n/pt.ts"

// A conta fala com a API do mesmo jeito que o cadastro: `failureFrom` lê o
// corpo de erro da seção 12 e devolve um `SubmitFailure` com a mensagem, os
// erros de campo e o `request_id`.
export {
  failureFrom,
  visitReasons,
  visitorTypes,
  type SubmitFailure,
} from "@/features/registration/model.ts"

/**
 * Situação vigente de uma finalidade: um item de `current` em
 * `GET /v1/me/consents`. Sem aceite vigente, `granted` é falso e a versão e
 * a data chegam nulas.
 */
export type ConsentState = {
  purpose: string
  granted: boolean
  document_version: string | null
  granted_at: string | null
}

/**
 * Corpo de `GET /v1/me/consents` e da resposta de
 * `PUT /v1/me/consents/{purpose}` (SDD 12). `current` tem um item por
 * finalidade. `history` tem todas as linhas, da mais nova para a mais
 * antiga. A tela usa só `current`.
 */
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

/** Termos de Uso e Aviso de Privacidade. Obrigatório para ter conta. */
export const termsPurpose = "terms_and_privacy_notice"
/** Opcional: guardar tipo de visitante e motivo da visita (SDD 11.4). */
export const personalizationPurpose = "profile_personalization"
/** Opcional: deixar as conversas entrarem na avaliação (SDD 11.8). */
export const qualityPurpose = "quality_improvement"

/**
 * As duas finalidades que o membro liga e desliga na conta. Os Termos só
 * aceitam `true`, na tela de novo aceite, e `age_18_plus` não muda pela
 * conta: a API responde 422 às duas tentativas (SDD 12).
 */
export type OptionalPurpose =
  | typeof personalizationPurpose
  | typeof qualityPurpose

// Os caracteres que a seção 8.5 aceita no telefone: dígitos, `+`, `-`, `(`,
// `)` e espaço. O tamanho de 7 a 20 fica no `refine` do esquema.
const phonePattern = /^[0-9+\-() ]+$/

/**
 * Regras do formulário de perfil, as mesmas da seção 8.5. A tela valida com
 * este esquema pelo `zodResolver` antes do pedido, mas o servidor continua
 * sendo a autoridade (SDD 13.1) e devolve `field_errors` quando recusa.
 *
 * O resolver mostra o primeiro erro de cada campo, então a ordem das regras
 * decide a mensagem: nome vazio cai em `nameRequired`, nome com 1 caractere
 * cai em `nameInvalid`. `visitor_type` e `visit_reason` vêm de listas
 * fechadas na tela e por isso não têm regra aqui.
 */
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

/** Valores do formulário de perfil, inferidos do esquema. */
export type ProfileValues = z.infer<typeof profileSchema>

/** A parte do perfil (`Me`) de onde o formulário parte. */
export type ProfileSource = {
  full_name: string
  phone: string | null
  visitor_type: string | null
  visit_reason: string | null
}

/**
 * Valores do formulário a partir do perfil. Os campos de texto não aceitam
 * `null`, então um opcional ausente vira texto vazio.
 */
export function profileDefaults(me: ProfileSource): ProfileValues {
  return {
    full_name: me.full_name,
    phone: me.phone ?? "",
    visitor_type: me.visitor_type ?? "",
    visit_reason: me.visit_reason ?? "",
  }
}

/**
 * Monta o corpo de `PATCH /v1/me` a partir do formulário.
 *
 * Texto vazio vira `null`, que limpa o opcional no servidor (SDD 12). Só os
 * campos enviados mudam. Os campos sensíveis só seguem no pedido quando a
 * personalização está ativa: sem ela, a API recusaria um valor neles com
 * erro de campo (SDD 8.5). O e-mail nunca vai, porque não muda por aqui.
 */
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

/**
 * Situação vigente de uma finalidade, ou `null` enquanto os consentimentos
 * não carregaram ou quando a finalidade não veio na resposta.
 */
export function consentFor(
  consents: Consents | undefined,
  purpose: string,
): ConsentState | null {
  return consents?.current.find((item) => item.purpose === purpose) ?? null
}

/**
 * Diz se a finalidade tem aceite vigente. Sem dados carregados, devolve
 * falso: na dúvida, a tela trata o consentimento como desligado.
 */
export function isGranted(consents: Consents | undefined, purpose: string) {
  return consentFor(consents, purpose)?.granted === true
}

/**
 * A exclusão só vale com a palavra exata, sem espaços nas pontas. A
 * comparação diferencia maiúsculas: "excluir" não serve (SDD 15.5, Conta).
 */
export function deleteConfirmed(text: string) {
  return text.trim() === pt.account.privacy.deleteConfirmWord
}

/** Data curta em português, como "03 de nov. de 2026", no fuso local. */
export function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  })
}

/**
 * Texto da data de aceite ao lado de um interruptor: "Aceito em {date}",
 * ou "Desligado" sem data.
 */
export function grantedOn(iso: string | null | undefined) {
  if (!iso) {
    return pt.account.privacy.off
  }
  return pt.account.privacy.grantedOn.replace("{date}", formatDate(iso))
}
