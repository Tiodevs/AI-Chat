import { useState } from "react"
import { useNavigate, useSearchParams } from "react-router"

import { queryClient } from "@/app/query-client.ts"
import { pt } from "@/i18n/pt.ts"
import { api } from "@/lib/api/client.ts"

import { retryAfterFrom } from "./api-error.ts"
import { limitMessage, safeReturnTo } from "./return-to.ts"
import { meQuery } from "./useSession.ts"

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
      if (!result.response.ok || !result.data) {
        setError(pt.signIn.credentials)
        return
      }
      queryClient.setQueryData(meQuery.queryKey, result.data)
      await navigate(safeReturnTo(params.get("returnTo")))
    } catch {
      setError(pt.couldNotContinue)
    } finally {
      setPending(false)
    }
  }

  return { submit, pending, error }
}
