import { useQuery } from "@tanstack/react-query"

import { messageFrom } from "@/features/auth/api-error.ts"
import { meQuery } from "@/features/auth/useSession.ts"
import { pt } from "@/i18n/pt.ts"
import { api } from "@/lib/api/client.ts"

import { failureFrom, type RequestValues, type SubmitFailure } from "./model.ts"

export type SubmitResult =
  | { ok: true; dueAt: string }
  | SubmitFailure

export function usePrivacyRequest() {
  const me = useQuery(meQuery).data ?? null

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
        // O 429 do canal tem a própria cópia. O failureFrom usaria a do cadastro.
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
