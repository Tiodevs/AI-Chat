import { useState } from "react"
import { useNavigate } from "react-router"

import { queryClient } from "@/app/query-client.ts"
import { resetAskState } from "@/features/ask/store.ts"
import { pt } from "@/i18n/pt.ts"
import { api } from "@/lib/api/client.ts"

import { meQuery } from "./useSession.ts"

/** Encerra a sessão na API e limpa o que a tela guardou da conta. */
export function useSignOut() {
  const navigate = useNavigate()
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function signOut() {
    if (pending) {
      return
    }
    setPending(true)
    setError(null)
    try {
      const result = await api.POST("/v1/auth/logout")
      // 401 quer dizer que a sessão já tinha acabado: o resultado é o mesmo.
      if (!result.response.ok && result.response.status !== 401) {
        setError(pt.profile.signOutFailed)
        return
      }
      queryClient.clear()
      queryClient.setQueryData(meQuery.queryKey, null)
      resetAskState()
      await navigate("/", { replace: true })
    } catch {
      setError(pt.profile.signOutFailed)
    } finally {
      setPending(false)
    }
  }

  return { signOut, pending, error }
}
