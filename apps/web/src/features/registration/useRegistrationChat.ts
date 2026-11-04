import { useCallback, useEffect, useState } from "react"
import { useNavigate } from "react-router"

import { queryClient } from "@/app/query-client.ts"
import { meQuery } from "@/features/auth/useSession.ts"
import { pt } from "@/i18n/pt.ts"
import { api } from "@/lib/api/client.ts"
import type { components } from "@/lib/api/schema.ts"

import {
  failureFrom,
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

export type ChatNotice = {
  message: string
  requestId: string | null
  /** O provedor de IA está fora. A tela oferece o formulário. */
  unavailable: boolean
  /** Texto que falhou, para tentar de novo. */
  retryText: string | null
}

export function useRegistrationChat() {
  const navigate = useNavigate()
  const [session, setSession] = useState<RegistrationSession | null>(null)
  const [loading, setLoading] = useState(true)
  const [pending, setPending] = useState(false)
  const [notice, setNotice] = useState<ChatNotice | null>(null)
  const [outgoing, setOutgoing] = useState<string | null>(null)
  const [documentVersion, setDocumentVersion] = useState<string | null>(null)
  const [actionErrors, setActionErrors] = useState<Record<string, string>>({})

  const fail = useCallback(
    (error: unknown, status: number, retryText: string | null = null) => {
      const failure = failureFrom(error, status)
      setNotice({
        message:
          status === 503 ? pt.registration.unavailable : failure.message,
        requestId: failure.requestId,
        unavailable: status === 503,
        retryText,
      })
    },
    []
  )

  const crash = useCallback((retryText: string | null = null) => {
    setNotice({
      message: pt.couldNotContinue,
      requestId: null,
      unavailable: false,
      retryText,
    })
  }, [])

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
        if (!started.response.ok || !started.data) {
          fail(started.error, started.response.status)
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
          crash()
        }
      } finally {
        if (!signal.aborted) {
          setLoading(false)
        }
      }
    }

    void load()
    return () => controller.abort()
  }, [crash, fail, remember])

  async function send(text: string) {
    if (!session || pending || !text.trim()) {
      return false
    }
    const trimmed = text.trim()
    setPending(true)
    setNotice(null)
    setOutgoing(trimmed)
    try {
      const result = await api.POST(
        "/v1/registration/sessions/{session_id}/messages",
        {
          params: { path: { session_id: session.id } },
          body: { text: trimmed },
        }
      )
      if (!result.response.ok || !result.data) {
        fail(result.error, result.response.status, trimmed)
        return false
      }
      remember(asSession(result.data))
      return true
    } catch {
      crash(trimmed)
      return false
    } finally {
      setOutgoing(null)
      setPending(false)
    }
  }

  async function editField(field: FieldName, value: string | null) {
    if (!session || pending) {
      return false
    }
    setPending(true)
    setNotice(null)
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
      if (!result.response.ok || !result.data) {
        fail(result.error, result.response.status)
        return false
      }
      remember(asSession(result.data))
      return true
    } catch {
      crash()
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
    setNotice(null)
    try {
      const result = await api.POST(
        "/v1/registration/sessions/{session_id}/password",
        {
          params: { path: { session_id: session.id } },
          body: { password },
        }
      )
      if (!result.response.ok || !result.data) {
        fail(result.error, result.response.status)
        return
      }
      remember(asSession(result.data))
    } catch {
      crash()
    } finally {
      setPending(false)
    }
  }

  async function review(accept: boolean) {
    if (!session || pending) {
      return
    }
    setPending(true)
    setNotice(null)
    try {
      const result = await api.POST(
        "/v1/registration/sessions/{session_id}/review",
        {
          params: { path: { session_id: session.id } },
          body: { accept },
        }
      )
      if (!result.response.ok || !result.data) {
        fail(result.error, result.response.status)
        return
      }
      remember(asSession(result.data))
    } catch {
      crash()
    } finally {
      setPending(false)
    }
  }

  async function accept(consents: Consents) {
    if (!session || pending) {
      return
    }
    if (!documentVersion) {
      crash()
      return
    }
    setPending(true)
    setNotice(null)
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
        if (Object.keys(failure.fieldErrors).length === 0) {
          fail(result.error, result.response.status)
        }
        return
      }
      sessionStorage.removeItem(SESSION_KEY)
      queryClient.setQueryData(meQuery.queryKey, result.data)
      await navigate("/account")
    } catch {
      crash()
    } finally {
      setPending(false)
    }
  }

  return {
    session,
    loading,
    pending,
    notice,
    outgoing,
    dismissNotice: () => setNotice(null),
    actionErrors,
    send,
    skip: () => send(pt.registration.skipMessage),
    editField,
    setPassword,
    review,
    accept,
  }
}
