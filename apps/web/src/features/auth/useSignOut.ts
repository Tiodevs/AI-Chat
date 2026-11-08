/**
 * Controlador da saída da conta. Seções 10.3 e 14.6 do SDD
 * (`ProfileButton`).
 *
 * Usado por `app/shell.tsx`, que liga `signOut` ao item Sair do menu do
 * perfil. Usa o cliente tipado (`lib/api/client.ts`), o `queryClient` e o
 * `resetAskState` do store da conversa.
 */
import { useState } from "react"
import { useNavigate } from "react-router"

import { queryClient } from "@/app/query-client.ts"
import { resetAskState } from "@/features/ask/store.ts"
import { pt } from "@/i18n/pt.ts"
import { api } from "@/lib/api/client.ts"

import { meQuery } from "./useSession.ts"

/**
 * Encerra a sessão na API e limpa o que a tela guardou da conta.
 *
 * 1. Ignora um clique enquanto a saída anterior não terminou.
 * 2. Faz `POST /v1/auth/logout`, que revoga a sessão e apaga o cookie
 *    `atrium_session` (seção 10.3).
 * 3. Limpa todo o cache do TanStack Query e grava `null` no `me`, para o
 *    shell saber na hora que não há sessão, sem pedir `GET /v1/me`.
 * 4. Esvazia o store da conversa, o que aborta os fluxos em andamento.
 * 5. Volta para `/` com `replace`, que troca a entrada atual do histórico:
 *    o Voltar do navegador não retorna à página onde a pessoa saiu.
 *
 * Se a API falhar, a sessão continua e `error` avisa (seção 14.6). O
 * cookie `atrium_guest` continua no navegador; a Etapa 15.1 passa a
 * apagá-lo na saída.
 */
export function useSignOut() {
  const navigate = useNavigate()
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function signOut() {
    // 1.
    if (pending) {
      return
    }
    setPending(true)
    setError(null)
    try {
      // 2.
      const result = await api.POST("/v1/auth/logout")
      // 401 quer dizer que a sessão já tinha acabado: o resultado é o mesmo.
      if (!result.response.ok && result.response.status !== 401) {
        setError(pt.profile.signOutFailed)
        return
      }
      // 3.
      queryClient.clear()
      queryClient.setQueryData(meQuery.queryKey, null)
      // 4.
      resetAskState()
      // 5.
      await navigate("/", { replace: true })
    } catch {
      setError(pt.profile.signOutFailed)
    } finally {
      setPending(false)
    }
  }

  return { signOut, pending, error }
}
