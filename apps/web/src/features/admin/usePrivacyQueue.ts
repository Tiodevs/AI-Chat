import { useQuery } from "@tanstack/react-query"
import { useState } from "react"

import { queryClient } from "@/app/query-client.ts"
import {
  fieldErrorsFrom,
  messageFrom,
  requestIdFrom,
} from "@/features/auth/api-error.ts"
import { pt } from "@/i18n/pt.ts"
import { api } from "@/lib/api/client.ts"

import type { PrivacyQueue, PrivacyQueueItem, RequestStatus } from "./privacy-queue-model.ts"

export const privacyQueueQuery = {
  queryKey: ["admin", "privacy-requests"] as const,
  queryFn: loadQueue,
}

export type UpdateResult =
  | { ok: true; request: PrivacyQueueItem }
  | {
      ok: false
      message: string
      fieldErrors: Record<string, string>
      requestId: string | null
    }

async function loadQueue(): Promise<PrivacyQueue> {
  const result = await api.GET("/v1/admin/privacy/requests")
  if (!result.response.ok || !result.data) {
    throw new Error(messageFrom(result.error, pt.privacyQueue.table.loadFailed))
  }
  return result.data
}

/** Fila de pedidos de titular do admin. SDD 11.5, 12 e 15.5. */
export function usePrivacyQueue() {
  const queue = useQuery(privacyQueueQuery)
  const [openId, setOpenId] = useState<string | null>(null)

  async function update(
    id: string,
    change: { status: RequestStatus; resolutionNote: string },
  ): Promise<UpdateResult> {
    try {
      const note = change.resolutionNote.trim()
      const result = await api.PATCH("/v1/admin/privacy/requests/{request_id}", {
        params: { path: { request_id: id } },
        // Nota vazia mantém a nota atual no servidor.
        body: { status: change.status, resolution_note: note === "" ? null : note },
      })
      if (!result.response.ok || !result.data) {
        return {
          ok: false,
          message: messageFrom(result.error, pt.couldNotContinue),
          fieldErrors: fieldErrorsFrom(result.error),
          requestId: requestIdFrom(result.error),
        }
      }
      await queryClient.invalidateQueries({ queryKey: privacyQueueQuery.queryKey })
      return { ok: true, request: result.data }
    } catch {
      return { ok: false, message: pt.couldNotContinue, fieldErrors: {}, requestId: null }
    }
  }

  return {
    queue: queue.data,
    loading: queue.isPending,
    loadError: queue.isError,
    openId,
    open: setOpenId,
    update,
  }
}

export type PrivacyQueueModel = ReturnType<typeof usePrivacyQueue>
