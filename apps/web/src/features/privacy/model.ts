/**
 * Modelo do Aviso de Privacidade e do canal do titular: os tipos de pedido,
 * as âncoras das seções do Aviso, as regras do formulário do canal e o
 * texto do prazo. Só funções puras, sem React e sem rede.
 *
 * Quem usa: `privacy-screen.tsx` e `usePrivacyRequest.ts`. Usa o `pt` de
 * `i18n/pt.ts` e reaproveita o mapa de erros do cadastro
 * (`features/registration/model.ts`).
 *
 * SDD 11.5 (direitos do titular), 11.11 (documentos de privacidade), 12
 * (`POST /v1/privacy/requests`) e 15.5 (Privacidade).
 */
import { z } from "zod"

import { pt } from "@/i18n/pt.ts"

// O canal lê os erros da API do mesmo jeito que o cadastro: `failureFrom`
// devolve um `SubmitFailure` com a mensagem, os erros de campo e o
// `request_id`.
export {
  failureFrom,
  type SubmitFailure,
} from "@/features/registration/model.ts"

/**
 * Os tipos de pedido do canal, na ordem dos botões. São os direitos do
 * art. 18 que o canal recebe (SDD 11.5), e a API aceita exatamente esta
 * lista em `request_type`.
 */
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

/** Um dos tipos de `requestTypes`. */
export type RequestType = (typeof requestTypes)[number]

/**
 * As seções do Aviso, na ordem da página (SDD 15.5, Privacidade). `id` é a
 * âncora da URL e o `id` da `<section>`. `key` aponta para o texto em
 * `pt.privacyNotice.sections`. A conta leva direto ao canal pela âncora
 * `pedidos`.
 */
export const noticeSections = [
  { id: "quem-cuida", key: "controller" },
  { id: "dados", key: "data" },
  { id: "saude", key: "health" },
  { id: "whatsapp", key: "whatsapp" },
  { id: "compartilhamento", key: "processors" },
  { id: "retencao", key: "retention" },
  { id: "direitos", key: "rights" },
  { id: "cookies", key: "cookies" },
  { id: "seguranca", key: "security" },
  { id: "incidentes", key: "incidents" },
  { id: "pedidos", key: "channel" },
] as const

// Só confere a forma geral de um e-mail. A regra estrita, com só letras,
// números e `. _ + -` antes e depois do `@`, fica no servidor, que devolve
// o erro no campo (SDD 12).
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/**
 * Regras do formulário do canal, adiantadas no navegador: e-mail com forma
 * válida, um tipo da lista e descrição de 1 a 2.000 caracteres depois de
 * tirar os espaços das pontas (SDD 12). O servidor continua sendo a
 * autoridade: ele também recusa caracteres de controle e o e-mail fora do
 * padrão seguro, com `field_errors`.
 */
export const requestSchema = z.object({
  contact_email: z
    .string()
    .trim()
    .regex(emailPattern, pt.privacyRequest.emailInvalid),
  request_type: z
    .string()
    .refine(
      (value) => requestTypes.some((item) => item === value),
      pt.privacyRequest.typeRequired
    ),
  description: z
    .string()
    .trim()
    .min(1, pt.privacyRequest.descriptionRequired)
    .max(2000, pt.privacyRequest.descriptionTooLong),
})

/** Valores do formulário do canal, inferidos do esquema. */
export type RequestValues = z.infer<typeof requestSchema>

/**
 * Formulário vazio. Com sessão, o e-mail do membro já vem preenchido, e a
 * pessoa pode trocá-lo por outro endereço para a resposta.
 */
export function emptyRequest(email: string | null | undefined): RequestValues {
  return { contact_email: email ?? "", request_type: "", description: "" }
}

/**
 * Confirmação do envio com o prazo por extenso, como "18 de novembro de
 * 2026". O prazo é o `due_at` da resposta, 15 dias corridos depois do
 * recebimento (SDD 11.5).
 */
export function sentMessage(dueAt: string) {
  const date = new Date(dueAt).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  })
  return pt.privacyRequest.sent.replace("{date}", date)
}
