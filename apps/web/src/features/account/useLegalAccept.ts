import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useNavigate, useSearchParams } from "react-router"

import { queryClient } from "@/app/query-client.ts"
import { safeReturnTo } from "@/features/auth/return-to.ts"
import { meQuery, type Me } from "@/features/auth/useSession.ts"
import { legalVersionsQuery } from "@/features/privacy/useLegalVersions.ts"
import { api } from "@/lib/api/client.ts"

import { failureFrom, termsPurpose, type SubmitFailure } from "./model.ts"

export function useLegalAccept(me: Me) {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const version = useQuery(legalVersionsQuery)
  const [pending, setPending] = useState(false)
  const [failure, setFailure] = useState<SubmitFailure | null>(null)
  const returnTo = safeReturnTo(params.get("returnTo"))

  async function accept() {
    setPending(true)
    setFailure(null)
    try {
      const result = await api.PUT("/v1/me/consents/{purpose}", {
        params: { path: { purpose: termsPurpose } },
        body: { granted: true },
      })
      if (!result.response.ok) {
        setFailure(failureFrom(result.error, result.response.status))
        return
      }
      queryClient.setQueryData(meQuery.queryKey, {
        ...me,
        needs_legal_acceptance: false,
      })
      await navigate(returnTo, { replace: true })
    } catch {
      setFailure(failureFrom(null, 0))
    } finally {
      setPending(false)
    }
  }

  return {
    version: version.data?.terms ?? null,
    needsAcceptance: me.needs_legal_acceptance,
    returnTo,
    pending,
    failure,
    accept,
  }
}
