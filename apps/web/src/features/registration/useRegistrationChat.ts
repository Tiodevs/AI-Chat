import { useCallback, useEffect, useState } from "react"
import { useNavigate } from "react-router"

import { queryClient } from "@/app/query-client.ts"
import { meQuery } from "@/features/auth/useSession.ts"
import { pt } from "@/i18n/pt.ts"
import { api } from "@/lib/api/client.ts"
import type { components } from "@/lib/api/schema.ts"

import {
  failureFrom,
  formPath,
  sessionIdFrom,
  type Consents,
  type FieldName,
  type RegistrationSession,
} from "./model.ts"

const SESSION_KEY = "atrium.registration-session"

type SessionResponse = components["schemas"]["RegistrationSessionResponse"]

function asSession(data: SessionResponse): RegistrationSession {
  return {
    id: data.id,
    status: data.status,
    path: data.path,
    fields: data.fields,
    field_errors: data.field_errors,
    next_step: data.next_step,
    prompt: data.prompt,
    messages: data.messages.map((message) => ({
      role: message.role,
      text: message.text,
      created_at: message.created_at,
    })),
    expires_at: data.expires_at,
  }
}

function resumable(status: string) {
  return status !== "completed" && status !== "abandoned"
}

export function useRegistrationChat() {
  const navigate = useNavigate()
  const [session, setSession] = useState<RegistrationSession | null>(null)
  const [loading, setLoading] = useState(true)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [requestId, setRequestId] = useState<string | null>(null)
  const [documentVersion, setDocumentVersion] = useState<string | null>(null)
  const [actionErrors, setActionErrors] = useState<Record<string, string>>({})

  const remember = useCallback((next: RegistrationSession) => {
    sessionStorage.setItem(SESSION_KEY, next.id)
    setSession(next)
    setActionErrors({})
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    const signal = controller.signal

    async function load() {
      async function openStarted(started: {
        response: { status: number; ok: boolean }
        data?: SessionResponse
        error?: unknown
      }) {
        if (started.response.status === 503) {
          await navigate(formPath(null, true), { replace: true })
          return
        }
        if (!started.response.ok || !started.data) {
          const failure = failureFrom(started.error, started.response.status)
          setError(failure.message)
          setRequestId(failure.requestId)
          return
        }
        remember(asSession(started.data))
      }

      try {
        const stored = sessionIdFrom(sessionStorage.getItem(SESSION_KEY))
        const legalRequest = api.GET("/v1/legal/versions", { signal })
        if (!stored) {
          const [legal, started] = await Promise.all([
            legalRequest,
            api.POST("/v1/registration/sessions", { signal }),
          ])
          if (signal.aborted) {
            return
          }
          if (legal.data?.terms) {
            setDocumentVersion(legal.data.terms)
          }
          await openStarted(started)
          return
        }
        const [legal, existing] = await Promise.all([
          legalRequest,
          api.GET("/v1/registration/sessions/{session_id}", {
            signal,
            params: { path: { session_id: stored } },
          }),
        ])
        if (signal.aborted) {
          return
        }
        if (legal.data?.terms) {
          setDocumentVersion(legal.data.terms)
        }
        if (existing.response.status === 503) {
          await navigate(formPath(stored, true), { replace: true })
          return
        }
        if (existing.data && resumable(existing.data.status)) {
          remember(asSession(existing.data))
          return
        }
        const started = await api.POST("/v1/registration/sessions", { signal })
        if (signal.aborted) {
          return
        }
        await openStarted(started)
      } catch {
        if (!signal.aborted) {
          setError(pt.couldNotContinue)
        }
      } finally {
        if (!signal.aborted) {
          setLoading(false)
        }
      }
    }

    void load()
    return () => controller.abort()
  }, [navigate, remember])

  async function send(text: string) {
    if (!session || pending || !text.trim()) {
      return false
    }
    setPending(true)
    setError(null)
    setRequestId(null)
    try {
      const result = await api.POST(
        "/v1/registration/sessions/{session_id}/messages",
        {
          params: { path: { session_id: session.id } },
          body: { text: text.trim() },
        }
      )
      if (result.response.status === 503) {
        await navigate(formPath(session.id, true), { replace: true })
        return false
      }
      if (!result.response.ok || !result.data) {
        const failure = failureFrom(result.error, result.response.status)
        setError(failure.message)
        setRequestId(failure.requestId)
        return false
      }
      remember(asSession(result.data))
      return true
    } catch {
      setError(pt.couldNotContinue)
      return false
    } finally {
      setPending(false)
    }
  }

  async function editField(field: FieldName, value: string | null) {
    if (!session || pending) {
      return false
    }
    setPending(true)
    setError(null)
    try {
      const body: components["schemas"]["FieldsPatchRequest"] = {
        [field]: value,
      }
      const result = await api.PATCH(
        "/v1/registration/sessions/{session_id}/fields",
        {
          params: { path: { session_id: session.id } },
          body,
        }
      )
      if (result.response.status === 503) {
        await navigate(formPath(session.id, true), { replace: true })
        return false
      }
      if (!result.response.ok || !result.data) {
        const failure = failureFrom(result.error, result.response.status)
        setError(failure.message)
        setRequestId(failure.requestId)
        return false
      }
      remember(asSession(result.data))
      return true
    } catch {
      setError(pt.couldNotContinue)
      return false
    } finally {
      setPending(false)
    }
  }

  async function setPassword(password: string) {
    if (!session || pending) {
      return
    }
    setPending(true)
    setError(null)
    try {
      const result = await api.POST(
        "/v1/registration/sessions/{session_id}/password",
        {
          params: { path: { session_id: session.id } },
          body: { password },
        }
      )
      if (!result.response.ok || !result.data) {
        const failure = failureFrom(result.error, result.response.status)
        setError(failure.message)
        setRequestId(failure.requestId)
        return
      }
      remember(asSession(result.data))
    } catch {
      setError(pt.couldNotContinue)
    } finally {
      setPending(false)
    }
  }

  async function review(accept: boolean) {
    if (!session || pending) {
      return
    }
    setPending(true)
    setError(null)
    try {
      const result = await api.POST(
        "/v1/registration/sessions/{session_id}/review",
        {
          params: { path: { session_id: session.id } },
          body: { accept },
        }
      )
      if (!result.response.ok || !result.data) {
        const failure = failureFrom(result.error, result.response.status)
        setError(failure.message)
        setRequestId(failure.requestId)
        return
      }
      remember(asSession(result.data))
    } catch {
      setError(pt.couldNotContinue)
    } finally {
      setPending(false)
    }
  }

  async function accept(consents: Consents) {
    if (!session || pending) {
      return
    }
    if (!documentVersion) {
      setError(pt.couldNotContinue)
      return
    }
    setPending(true)
    setError(null)
    setActionErrors({})
    try {
      const result = await api.POST(
        "/v1/registration/sessions/{session_id}/acceptance",
        {
          params: { path: { session_id: session.id } },
          body: {
            accept_terms: consents.accept_terms,
            document_version: documentVersion,
            age_18_plus: consents.age_18_plus,
            profile_personalization: consents.profile_personalization,
            quality_improvement: consents.quality_improvement,
          },
        }
      )
      if (!result.response.ok || !result.data) {
        const failure = failureFrom(result.error, result.response.status)
        setActionErrors(failure.fieldErrors)
        setRequestId(failure.requestId)
        if (Object.keys(failure.fieldErrors).length === 0) {
          setError(failure.message)
        }
        return
      }
      sessionStorage.removeItem(SESSION_KEY)
      queryClient.setQueryData(meQuery.queryKey, result.data)
      await navigate("/account")
    } catch {
      setError(pt.couldNotContinue)
    } finally {
      setPending(false)
    }
  }

  return {
    session,
    loading,
    pending,
    error,
    requestId,
    actionErrors,
    send,
    skip: () => send(pt.registration.skipMessage),
    editField,
    setPassword,
    review,
    accept,
  }
}
