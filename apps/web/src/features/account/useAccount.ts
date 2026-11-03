import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "react-router"

import { queryClient } from "@/app/query-client.ts"
import { meQuery, type Me } from "@/features/auth/useSession.ts"
import { pt } from "@/i18n/pt.ts"
import { api } from "@/lib/api/client.ts"

import {
  failureFrom,
  isGranted,
  personalizationPurpose,
  profilePatch,
  type Consents,
  type OptionalPurpose,
  type ProfileValues,
  type SubmitFailure,
} from "./model.ts"

export const consentsQuery = {
  queryKey: ["me", "consents"] as const,
  queryFn: loadConsents,
}

export const conversationsQuery = {
  queryKey: ["me", "conversations"] as const,
  queryFn: loadConversations,
}

async function loadConsents(): Promise<Consents> {
  const result = await api.GET("/v1/me/consents")
  if (!result.response.ok || !result.data) {
    throw new Error(failureFrom(result.error, result.response.status).message)
  }
  return result.data
}

async function loadConversations() {
  const result = await api.GET("/v1/conversations")
  if (!result.response.ok || !result.data) {
    throw new Error(failureFrom(result.error, result.response.status).message)
  }
  return result.data.conversations
}

function networkFailure(): SubmitFailure {
  return {
    ok: false,
    status: 0,
    message: pt.couldNotContinue,
    fieldErrors: {},
    requestId: null,
  }
}

function saveFile(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export function useAccount(me: Me) {
  const navigate = useNavigate()
  const consents = useQuery(consentsQuery)
  const conversations = useQuery(conversationsQuery)
  const [changingPurpose, setChangingPurpose] = useState<string | null>(null)

  async function saveProfile(
    values: ProfileValues,
  ): Promise<SubmitFailure | null> {
    try {
      const body = profilePatch(
        values,
        isGranted(consents.data, personalizationPurpose),
      )
      const result = await api.PATCH("/v1/me", { body })
      if (!result.response.ok || !result.data) {
        return failureFrom(result.error, result.response.status)
      }
      queryClient.setQueryData(meQuery.queryKey, result.data)
      return null
    } catch {
      return networkFailure()
    }
  }

  async function setConsent(
    purpose: OptionalPurpose,
    granted: boolean,
  ): Promise<SubmitFailure | null> {
    setChangingPurpose(purpose)
    try {
      const result = await api.PUT("/v1/me/consents/{purpose}", {
        params: { path: { purpose } },
        body: { granted },
      })
      if (!result.response.ok || !result.data) {
        return failureFrom(result.error, result.response.status)
      }
      queryClient.setQueryData(consentsQuery.queryKey, result.data)
      if (purpose === personalizationPurpose) {
        await queryClient.invalidateQueries({ queryKey: meQuery.queryKey })
      }
      return null
    } catch {
      return networkFailure()
    } finally {
      setChangingPurpose(null)
    }
  }

  async function exportData(): Promise<SubmitFailure | null> {
    try {
      const result = await api.GET("/v1/me/export", { parseAs: "blob" })
      if (!result.response.ok || !result.data) {
        return failureFrom(result.error, result.response.status)
      }
      saveFile(result.data, "atrium-meus-dados.json")
      return null
    } catch {
      return networkFailure()
    }
  }

  async function deleteAccount(): Promise<SubmitFailure | null> {
    try {
      const result = await api.DELETE("/v1/me")
      if (!result.response.ok) {
        return failureFrom(result.error, result.response.status)
      }
      queryClient.clear()
      queryClient.setQueryData(meQuery.queryKey, null)
      await navigate("/")
      return null
    } catch {
      return networkFailure()
    }
  }

  return {
    me,
    consents,
    conversations,
    changingPurpose,
    saveProfile,
    setConsent,
    exportData,
    deleteAccount,
  }
}

export type AccountModel = ReturnType<typeof useAccount>
