/**
 * Dados da tela `/admin/attendance`: os atendimentos encerrados e a
 * leitura de um deles com motivo. Seções 29.10 e 29.11 do SDD (J11).
 *
 * Usado por `app/routes/admin-attendance.tsx`. A lista vem do cache do
 * TanStack Query, como as outras telas de admin, e não tem conteúdo. A
 * leitura de um encerrado é `POST /v1/admin/handoffs/{id}/view`, que grava
 * `handoff.view` com o motivo na mesma transação (FR-26).
 */
import { useQuery } from "@tanstack/react-query"
import { useState } from "react"

import { fieldErrorsFrom, messageFrom } from "@/features/auth/api-error.ts"
import { pt } from "@/i18n/pt.ts"
import { api } from "@/lib/api/client.ts"

import { detailView, type DetailView } from "./model.ts"

/** Uma linha da lista, sem conteúdo. */
export type ClosedRow = {
  id: string
  label: string
  trigger: string
  requestedAt: string
  assignedAt: string | null
  closedAt: string | null
  closeReason: string | null
  messageCount: number
  contentPurged: boolean
}

/** O resultado de abrir um encerrado. */
export type ViewResult =
  | { ok: true; detail: DetailView }
  | { ok: false; message: string; reasonError: string | null }

/** O período da lista e a lista dele. */
export function useClosedHandoffs() {
  const [period, setPeriod] = useState<7 | 30>(7)
  const query = useQuery({
    queryKey: ["admin", "handoffs", period] as const,
    queryFn: async (): Promise<ClosedRow[]> => {
      const result = await api.GET("/v1/admin/handoffs", {
        params: { query: { period_days: period } },
      })
      if (!result.response.ok || !result.data) {
        throw new Error(messageFrom(result.error, pt.couldNotContinue))
      }
      return result.data.handoffs.map((row) => ({
        id: row.id,
        label: row.label,
        trigger: row.trigger,
        requestedAt: row.requested_at,
        assignedAt: row.assigned_at,
        closedAt: row.closed_at,
        closeReason: row.close_reason,
        messageCount: row.message_count,
        contentPurged: row.content_purged,
      }))
    },
  })

  /** Abre o encerrado com o motivo. Fora de 10 a 500 caracteres, 422. */
  async function view(handoffId: string, reason: string): Promise<ViewResult> {
    try {
      const result = await api.POST("/v1/admin/handoffs/{handoff_id}/view", {
        params: { path: { handoff_id: handoffId } },
        body: { reason },
      })
      if (result.data) {
        return { ok: true, detail: detailView(result.data) }
      }
      return {
        ok: false,
        message: messageFrom(result.error, pt.couldNotContinue),
        reasonError: fieldErrorsFrom(result.error).reason ?? null,
      }
    } catch {
      return { ok: false, message: pt.couldNotContinue, reasonError: null }
    }
  }

  return {
    period,
    setPeriod,
    rows: query.data,
    loading: query.isPending,
    error: query.error ? query.error.message : null,
    view,
  }
}
