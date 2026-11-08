/**
 * Controlador do login (`/sign-in`). Seções 10.3, 10.4, 13.3 e 15.5 do
 * SDD.
 *
 * Usado por `app/routes/sign-in.tsx`, que passa `submit`, `pending` e
 * `error` ao `SignInForm`. Usa o cliente tipado (`lib/api/client.ts`), o
 * cache do `meQuery` e `safeReturnTo`.
 */
import { useState } from "react"
import { useNavigate, useSearchParams } from "react-router"

import { queryClient } from "@/app/query-client.ts"
import { pt } from "@/i18n/pt.ts"
import { api } from "@/lib/api/client.ts"

import { retryAfterFrom } from "./api-error.ts"
import { limitMessage, safeReturnTo } from "./return-to.ts"
import { meQuery } from "./useSession.ts"

/**
 * Hook do login.
 *
 * `submit` faz `POST /v1/auth/login`. No sucesso, a API define o cookie
 * `atrium_session` (seção 10.3) e devolve o perfil, que vai para o cache do
 * `meQuery`. Então navega:
 * 1. para `/legal/accept?returnTo=...`, se há documento legal novo a
 *    aceitar (seção 13.3);
 * 2. senão, para o `returnTo` da URL, já filtrado por `safeReturnTo`.
 *
 * O 429 mostra o limite em minutos (seção 10.4). Os outros erros mostram
 * a mensagem de credenciais (seção 15.5), e a falha de rede, o texto
 * genérico. O cookie `atrium_guest` continua; a Etapa 15.1 passa a apagá-lo
 * no login.
 */
export function useSignIn() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(values: { email: string; password: string }) {
    setPending(true)
    setError(null)
    try {
      const result = await api.POST("/v1/auth/login", { body: values })
      if (result.response.status === 429) {
        setError(limitMessage(retryAfterFrom(result.error) ?? 60))
        return
      }
      // Hoje até um 500 ou um 503 aparece como credencial errada. A Etapa
      // 14.1 deixa essa mensagem só para o 400 e o 401.
      if (!result.response.ok || !result.data) {
        setError(pt.signIn.credentials)
        return
      }
      queryClient.setQueryData(meQuery.queryKey, result.data)
      const returnTo = safeReturnTo(params.get("returnTo"))
      // 1.
      if (result.data.needs_legal_acceptance) {
        await navigate(
          `/legal/accept?returnTo=${encodeURIComponent(returnTo)}`,
        )
        return
      }
      // 2.
      await navigate(returnTo)
    } catch {
      setError(pt.couldNotContinue)
    } finally {
      setPending(false)
    }
  }

  return { submit, pending, error }
}
