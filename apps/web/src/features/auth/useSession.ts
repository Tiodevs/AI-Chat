/**
 * A sessão de quem usa o app: a consulta de `GET /v1/me` no TanStack Query.
 * Seções 10.3, 12 e 13.3 do SDD.
 *
 * O arquivo exporta a consulta, não um hook. O nome começa com `use`, e a
 * regra do ESLint (`eslint.config.js`) só deixa os arquivos `use*.ts` das
 * features importarem `@/lib/api`.
 *
 * Quem lê com `useQuery`: `app/shell.tsx`, as rotas `account` e
 * `legal-accept` e o `usePrivacyRequest`. As guardas de `app/guards.ts`
 * leem com `ensureQueryData`. Quem escreve com `setQueryData`:
 * `useSignIn.ts`, `useSignOut.ts`, `useAccount.ts`, `useLegalAccept.ts` e
 * os dois hooks de `features/registration`, com o perfil que a API devolve.
 */
import { pt } from "@/i18n/pt.ts"
import { api } from "@/lib/api/client.ts"
import type { components } from "@/lib/api/schema.ts"

import { ApiRequestError, messageFrom, requestIdFrom } from "./api-error.ts"

/** Perfil de `GET /v1/me`, sem `password_hash` (seção 12). */
export type Me = components["schemas"]["ProfileResponse"]

/**
 * Opções da consulta do perfil, as mesmas para quem lê e para quem
 * escreve. A chave `["me"]` identifica o perfil no cache do TanStack Query.
 */
export const meQuery = {
  queryKey: ["me"] as const,
  queryFn: loadMe,
}

/**
 * Busca o perfil. Devolve `null` no 401: sem sessão é um visitante, não um
 * erro. Outra falha lança `ApiRequestError`, que o error boundary da rota
 * mostra com o `request_id`.
 *
 * As guardas usam o perfil que já está no cache, então uma sessão revogada
 * no servidor só aparece numa leitura nova. A Etapa 14.1 acrescenta o 401
 * global, que limpa o `me` e leva a `/sign-in?returnTo=`.
 */
export async function loadMe(): Promise<Me | null> {
  const result = await api.GET("/v1/me")
  if (result.response.status === 401) {
    return null
  }
  if (!result.response.ok || !result.data) {
    throw new ApiRequestError(
      messageFrom(result.error, pt.couldNotContinue),
      requestIdFrom(result.error),
      result.response.status,
    )
  }
  return result.data
}
