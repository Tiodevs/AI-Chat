import { useEffect, useState } from "react"
import { useNavigate, useSearchParams } from "react-router"

import { queryClient } from "@/app/query-client.ts"
import { meQuery } from "@/features/auth/useSession.ts"
import { pt } from "@/i18n/pt.ts"
import { api } from "@/lib/api/client.ts"

import {
  emptyFormValues,
  failureFrom,
  formValuesFromFields,
  sessionIdFrom,
  toFormPayload,
  unavailableFrom,
  type FormValues,
  type SubmitFailure,
} from "./model.ts"

const SESSION_KEY = "atrium.registration-session"

export function useRegistrationForm() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const sessionId = sessionIdFrom(params.get("session"))
  const unavailable = unavailableFrom(params.get("unavailable"))
  const [loading, setLoading] = useState(true)
  const [defaults, setDefaults] = useState(emptyFormValues)
  const [documentVersion, setDocumentVersion] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [requestId, setRequestId] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    const signal = controller.signal

    async function load() {
      try {
        const legalRequest = api.GET("/v1/legal/versions", { signal })
        const sessionRequest = sessionId
          ? api.GET("/v1/registration/sessions/{session_id}", {
              signal,
              params: { path: { session_id: sessionId } },
            })
          : null
        const [legal, existing] = await Promise.all([
          legalRequest,
          sessionRequest,
        ])
        if (signal.aborted) {
          return
        }
        if (legal.data?.terms) {
          setDocumentVersion(legal.data.terms)
        } else {
          const failure = failureFrom(legal.error, legal.response.status)
          setLoadError(failure.message)
          setRequestId(failure.requestId)
        }
        if (!existing) {
          return
        }
        if (existing.data) {
          setDefaults(formValuesFromFields(existing.data.fields))
          return
        }
        if (existing.response.status === 404) {
          setLoadError(pt.registration.sessionMissing)
          return
        }
        const failure = failureFrom(existing.error, existing.response.status)
        setLoadError(failure.message)
        setRequestId(failure.requestId)
      } catch {
        if (!signal.aborted) {
          setLoadError(pt.couldNotContinue)
        }
      } finally {
        if (!signal.aborted) {
          setLoading(false)
        }
      }
    }

    void load()
    return () => controller.abort()
  }, [sessionId])

  async function submit(values: FormValues): Promise<SubmitFailure | null> {
    if (!documentVersion) {
      return {
        ok: false,
        status: 0,
        message: pt.couldNotContinue,
        fieldErrors: {},
        requestId: null,
      }
    }
    try {
      const result = await api.POST("/v1/registration/form", {
        body: toFormPayload(values, documentVersion, sessionId),
      })
      if (!result.response.ok || !result.data) {
        return failureFrom(result.error, result.response.status)
      }
      sessionStorage.removeItem(SESSION_KEY)
      queryClient.setQueryData(meQuery.queryKey, result.data)
      await navigate("/account")
      return null
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

  return {
    loading,
    defaults,
    documentVersion,
    loadError,
    requestId,
    unavailable,
    sessionId,
    submit,
  }
}
