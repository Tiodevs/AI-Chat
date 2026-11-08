/**
 * Regras puras do cadastro: campos, passos, aceites, força da senha,
 * validação do formulário e a leitura das falhas da API. Seções 7.2 e 8.5
 * do SDD.
 *
 * Não faz pedido nem guarda estado. Usado pelos hooks e telas desta pasta,
 * por `ProfileSummaryCard`, `PasswordCard`, `ConsentFieldSet` e
 * `RegistrationStepper`, em `components/patterns`, e por `features/account`
 * e `features/privacy`, que reaproveitam `failureFrom` e as listas de
 * opções. Os textos vêm de `src/i18n/pt.ts`. A validação no navegador só
 * adianta o erro: o servidor continua sendo a autoridade (seção 13.1).
 */
import { z } from "zod"

import {
  fieldErrorsFrom,
  messageFrom,
  requestIdFrom,
  retryAfterFrom,
} from "@/features/auth/api-error.ts"
import { pt } from "@/i18n/pt.ts"

/**
 * As quatro etapas visíveis do `RegistrationStepper`: Dados, Senha, Revisão
 * e Aceite. O componente saiu da tela de cadastro em 2026-11-04 e ficou só
 * no Storybook (seção 14.6).
 */
export const registrationPhases = [
  "details",
  "password",
  "review",
  "agree",
] as const

/** Uma das etapas de `registrationPhases`. */
export type RegistrationPhase = (typeof registrationPhases)[number]

/**
 * Campos do cadastro na ordem da seção 7.2: os obrigatórios e depois os
 * opcionais. O cartão de resumo segue esta ordem.
 */
export const fieldNames = [
  "full_name",
  "email",
  "phone",
  "visitor_type",
  "visit_reason",
] as const

/** Nome de um campo do cadastro. */
export type FieldName = (typeof fieldNames)[number]

/** Valores aceitos de `visitor_type`, os mesmos da API (seção 8.5). */
export const visitorTypes = ["patient", "visitor", "caregiver"] as const

/** Um valor de `visitorTypes`. */
export type VisitorType = (typeof visitorTypes)[number]

/** Valores aceitos de `visit_reason`, sem texto livre (seção 8.5). */
export const visitReasons = [
  "visiting_someone",
  "own_appointment",
  "exam_or_test",
  "accompanying_someone",
  "administrative",
  "other",
] as const

/** Um valor de `visitReasons`. */
export type VisitReason = (typeof visitReasons)[number]

/** Passos que aceitam Pular: os campos opcionais da seção 7.2. */
const optionalSteps = ["phone", "visitor_type", "visit_reason"] as const

/**
 * Campos entendidos até agora, como o `fields` da resposta da sessão.
 * `null` é campo ainda sem valor.
 */
export type RegistrationFields = {
  full_name: string | null
  email: string | null
  phone: string | null
  visitor_type: string | null
  visit_reason: string | null
}

/** Uma fala da transcrição do chat. Não tem senha (seção 12). */
export type TranscriptMessage = {
  role: "user" | "assistant"
  text: string
  created_at: string
}

/**
 * Sessão do cadastro por chat, como a API a devolve a cada passo (seção
 * 12). O `next_step` decide o rodapé do chat: resposta livre, senha,
 * revisão ou aceite. `field_errors` traz o erro de cada campo, pelo nome.
 * `prompt` é a última fala do assistente.
 */
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

/**
 * Os quatro aceites da conclusão (seção 7.2). Termos e maioridade são
 * obrigatórios; a personalização e a melhoria do assistente são opcionais.
 */
export type Consents = {
  accept_terms: boolean
  age_18_plus: boolean
  profile_personalization: boolean
  quality_improvement: boolean
}

/**
 * Valores do formulário completo. Um opcional sem valor é `""` no
 * formulário e vira `null` em `toFormPayload`.
 */
export type FormValues = Consents & {
  full_name: string
  email: string
  phone: string
  visitor_type: string
  visit_reason: string
  password: string
}

/** Nível do medidor de força do `PasswordCard`. */
export type PasswordStrength =
  "empty" | "short" | "long" | "fair" | "good" | "strong"

/**
 * Falha de um envio, pronta para a tela: status, mensagem em português,
 * erros por campo e o `request_id`. `status` 0 marca uma falha sem resposta
 * da API, como a rede.
 */
export type SubmitFailure = {
  ok: false
  status: number
  message: string
  fieldErrors: Record<string, string>
  requestId: string | null
}

/**
 * UUID, o formato do id da sessão. Um valor estranho no `sessionStorage` ou
 * na URL é ignorado.
 */
const sessionIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

/**
 * Telefone da seção 8.5: de 7 a 20 caracteres entre dígitos, espaço e
 * `+ - ( )`.
 */
const phonePattern = /^[0-9+\-() ]{7,20}$/

/**
 * Trecho da mensagem de e-mail já cadastrado, `EMAIL_TAKEN` em
 * `apps/api/app/prompts/registration.py`. A API manda só o texto em
 * `field_errors.email`, sem código, e a tela reconhece o caso pelo trecho.
 * Se a frase mudar na API, o chat deixa de oferecer o botão Entrar.
 */
const takenPhrase = "já tem uma conta"

/**
 * Devolve o id se ele for um UUID, ou `null`. Protege contra um valor
 * adulterado no `sessionStorage` ou em `?session=`.
 */
export function sessionIdFrom(value: string | null) {
  if (!value || !sessionIdPattern.test(value)) {
    return null
  }
  return value
}

/** Lê o `?unavailable=1` da URL do formulário (veja `formPath`). */
export function unavailableFrom(value: string | null) {
  return value === "1"
}

/** O passo atual é um campo opcional, que a pessoa pode pular. */
export function canSkipStep(step: string) {
  return optionalSteps.some((item) => item === step)
}

/**
 * Traduz o `next_step` da API na etapa visível do `RegistrationStepper`.
 * Os passos de campo caem em `details`. Hoje só os testes a usam.
 */
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

/**
 * Fração da barra de progresso do `RegistrationStepper` (M11, seção 16.3):
 * 0,25 na primeira etapa e 1 na última.
 */
export function phaseScale(phase: RegistrationPhase) {
  const index = registrationPhases.indexOf(phase)
  return (index + 1) / registrationPhases.length
}

/** Todos os campos vazios, como numa sessão que acabou de começar. */
export function emptyFields(): RegistrationFields {
  return {
    full_name: null,
    email: null,
    phone: null,
    visitor_type: null,
    visit_reason: null,
  }
}

/** Quantos campos já têm valor. A contagem vai no botão do resumo. */
export function filledFieldCount(fields: RegistrationFields) {
  return fieldNames.filter((name) => fields[name]).length
}

/** Rótulo do campo em português. */
export function fieldLabel(name: FieldName) {
  return pt.registration.fields[name]
}

/**
 * Valor do campo para mostrar. Os enums viram o rótulo em português, e o
 * vazio vira `null`.
 */
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

/**
 * Texto da região ao vivo do `ProfileSummaryCard`: cada campo que ganhou um
 * valor novo, no formato `{field}: {value}`, separados por ponto. Vazio
 * quando nada mudou.
 */
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

/** A mensagem do campo é a de e-mail já cadastrado (veja `takenPhrase`). */
export function emailOffersSignIn(message: string | undefined) {
  return Boolean(message?.includes(takenPhrase))
}

/**
 * O envio do formulário falhou por e-mail já cadastrado: o 409 da seção 12
 * ou a mensagem em `field_errors.email`. A tela então oferece Entrar.
 */
export function failureOffersSignIn(failure: SubmitFailure) {
  return failure.status === 409 || emailOffersSignIn(failure.fieldErrors.email)
}

/**
 * Mede a senha para o medidor do `PasswordCard`. É só uma dica: a regra da
 * seção 8.5 é o tamanho, de 12 a 72, que a API confere.
 *
 * Fora do tamanho, o nível é `short` ou `long`. Dentro, conta as classes de
 * caractere (minúscula, maiúscula, dígito e símbolo): três ou mais é
 * `strong`, duas é `good`, uma é `fair`. O `score`, de 0 a 4, vira o
 * `aria-valuenow` do medidor.
 */
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

/**
 * Todos os aceites desmarcados. Os opcionais começam assim (seção 15.5,
 * Passo de aceite).
 */
export function emptyConsents(): Consents {
  return {
    accept_terms: false,
    age_18_plus: false,
    profile_personalization: false,
    quality_improvement: false,
  }
}

/**
 * Erros dos aceites obrigatórios que faltam. Objeto vazio quando os dois
 * estão marcados.
 */
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

/** Formulário vazio, com os aceites desmarcados. */
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

/**
 * Preenche o formulário com os campos entendidos no chat (jornada J4,
 * seção 15.3). A senha fica vazia, porque a API nunca a devolve (seção
 * 8.5), e os aceites começam desmarcados.
 */
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

/** Texto do limite de tentativas do cadastro, em minutos (seção 10.4). */
export function registrationLimitMessage(seconds: number) {
  const minutes = Math.max(1, Math.ceil(seconds / 60))
  if (minutes === 1) {
    return pt.registration.limitedOne
  }
  return pt.registration.limitedMany.replace("{minutes}", String(minutes))
}

/**
 * Converte a resposta de erro da API numa `SubmitFailure`.
 *
 * No 429, a mensagem vira o aviso em minutos, com `retry_after_seconds`.
 * Nos outros casos, vale a mensagem do envelope da seção 12 ou o texto
 * genérico. `features/account` e `features/privacy` usam a mesma função.
 */
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

/**
 * Caminho do formulário, com `?session=` para levar os campos do chat
 * (J4). `unavailable` acrescenta `?unavailable=1`, e a tela do formulário
 * avisa que o chat está indisponível. Nenhuma tela passa `unavailable`
 * hoje: o aviso do 503 fica na própria conversa (seção 15.5).
 */
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

/**
 * Texto sem espaços nas pontas, ou `null` se ficar vazio: a API espera
 * `null` num opcional sem valor.
 */
function emptyToNull(value: string) {
  const trimmed = value.trim()
  return trimmed ? trimmed : null
}

/**
 * Corpo de `POST /v1/registration/form`: os campos aparados, a senha como
 * foi digitada, a versão vigente dos documentos e os aceites. O
 * `session_id` é opcional e aponta a sessão do chat de onde a pessoa veio
 * (seção 12).
 */
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

/** Problema de validação do zod com a mensagem em português. */
function issue(message: string) {
  return { code: "custom" as const, message }
}

/**
 * Esquema zod do formulário, com as regras da seção 8.5 e as mensagens de
 * `pt.registration`. O `zodResolver` do react-hook-form roda este esquema
 * no envio e devolve os erros por campo.
 *
 * Cada campo usa `superRefine` para dar uma mensagem só: o vazio pede o
 * campo, e um valor fora da regra explica a regra. O `superRefine` do
 * objeto exige os dois aceites obrigatórios (seção 7.2) e põe cada erro no
 * campo dele, por `path`.
 */
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

/** Guarda de tipo: o texto é um dos `visitorTypes`. */
export function isVisitorType(value: string): value is VisitorType {
  return visitorTypes.some((item) => item === value)
}

/** Guarda de tipo: o texto é um dos `visitReasons`. */
export function isVisitReason(value: string): value is VisitReason {
  return visitReasons.some((item) => item === value)
}

/** Guarda de tipo: o texto é um dos `fieldNames`. Hoje não tem uso. */
export function isFieldName(value: string): value is FieldName {
  return fieldNames.some((item) => item === value)
}
