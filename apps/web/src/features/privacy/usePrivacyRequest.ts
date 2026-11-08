/**
 * Controlador do canal do titular: envia o pedido do formulário de
 * `/privacy` para `POST /v1/privacy/requests`.
 *
 * Camada: controller (SDD 13.2). Quem usa: `app/routes/privacy.tsx`, que
 * passa `email` e `submit` a `PrivacyScreen`. Usa o cliente `api`, o
 * `meQuery` (`features/auth/useSession.ts`), o `messageFrom` de
 * `features/auth/api-error.ts` e o `failureFrom` de `model.ts`.
 *
 * Qualquer pessoa pode pedir, com ou sem conta (FR-16). Com sessão, a API
 * liga o pedido ao membro pelo cookie, sem nada a mais no corpo. SDD 10.4
 * (limite de pedidos por IP), 11.5 (direitos do titular) e 12.
 */
import { useQuery } from "@tanstack/react-query"

import { messageFrom } from "@/features/auth/api-error.ts"
import { meQuery } from "@/features/auth/useSession.ts"
import { pt } from "@/i18n/pt.ts"
import { api } from "@/lib/api/client.ts"

import { failureFrom, type RequestValues, type SubmitFailure } from "./model.ts"

/** Resultado do envio: o prazo `due_at` no sucesso, ou a falha. */
export type SubmitResult =
  | { ok: true; dueAt: string }
  | SubmitFailure

/**
 * Prepara o envio do pedido.
 *
 * @returns `email`, o e-mail de quem está na conta (`null` sem sessão), e
 *   `submit`, que envia o pedido e nunca lança.
 */
export function usePrivacyRequest() {
  // O perfil vem do cache ou de `GET /v1/me`. Sem sessão, a API responde
  // 401, o `loadMe` devolve `null` e o formulário começa sem e-mail.
  const me = useQuery(meQuery).data ?? null

  /**
   * Envia o pedido, com o e-mail e a descrição sem espaços nas pontas. A API
   * responde 201 com `due_at`, 15 dias corridos depois do recebimento. Um
   * erro de campo volta em `fieldErrors`, e uma falha de rede vira a cópia
   * genérica.
   */
  async function submit(values: RequestValues): Promise<SubmitResult> {
    try {
      const result = await api.POST("/v1/privacy/requests", {
        body: {
          contact_email: values.contact_email.trim(),
          request_type: values.request_type,
          description: values.description.trim(),
        },
      })
      if (!result.response.ok || !result.data) {
        const failure = failureFrom(result.error, result.response.status)
        // O 429 do canal (o sexto pedido do mesmo IP no dia, SDD 10.4) tem a
        // própria cópia, que pede para tentar amanhã. O `failureFrom` usaria
        // a do cadastro, que conta minutos.
        if (result.response.status === 429) {
          return {
            ...failure,
            message: messageFrom(result.error, pt.couldNotContinue),
          }
        }
        return failure
      }
      return { ok: true, dueAt: result.data.due_at }
    } catch {
      return {
        ok: false,
        status: 0,
        message: pt.couldNotContinue,
        fieldErrors: {},
        requestId: null,
      }
    }
  }

  return { email: me?.email ?? null, submit }
}
