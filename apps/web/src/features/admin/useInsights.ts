import { useQuery } from "@tanstack/react-query"
import { useState } from "react"

import {
  fieldErrorsFrom,
  messageFrom,
  requestIdFrom,
} from "@/features/auth/api-error.ts"
import { pt } from "@/i18n/pt.ts"
import { api } from "@/lib/api/client.ts"

import type { Inspection, Overview, Period, Quality } from "./insights-model.ts"

export type QualityFilters = {
  period: Period
  outcome: string | null
  feedback: string | null
}

export type RevealResult =
  | { ok: true; fullName: string; email: string }
  | { ok: false; message: string; fieldErrors: Record<string, string>; requestId: string | null }

async function loadOverview(period: Period): Promise<Overview> {
  const result = await api.GET("/v1/admin/overview", {
    params: { query: { period_days: period } },
  })
  if (!result.response.ok || !result.data) {
    throw new Error(messageFrom(result.error, pt.insights.loadFailed))
  }
  return result.data
}

async function loadQuality(filters: QualityFilters): Promise<Quality> {
  const result = await api.GET("/v1/admin/quality", {
    params: {
      query: {
        period_days: filters.period,
        outcome: filters.outcome ?? undefined,
        feedback: filters.feedback ?? undefined,
      },
    },
  })
  if (!result.response.ok || !result.data) {
    throw new Error(messageFrom(result.error, pt.insights.loadFailed))
  }
  return result.data
}

async function loadInspection(id: string): Promise<Inspection> {
  const result = await api.GET("/v1/admin/conversations/{conversation_id}", {
    params: { path: { conversation_id: id } },
  })
  if (!result.response.ok || !result.data) {
    throw new Error(messageFrom(result.error, pt.quality.inspector.loadFailed))
  }
  return result.data
}

export function useOverview() {
  const [period, setPeriod] = useState<Period>(7)
  const overview = useQuery({
    queryKey: ["admin", "overview", period] as const,
    queryFn: () => loadOverview(period),
    placeholderData: (previous) => previous,
  })
  return {
    period,
    setPeriod,
    overview: overview.data,
    loading: overview.isPending,
    loadError: overview.isError,
  }
}

export type OverviewModel = ReturnType<typeof useOverview>

export function useQuality() {
  const [filters, setFilters] = useState<QualityFilters>({
    period: 7,
    outcome: null,
    feedback: null,
  })
  const [openId, setOpenId] = useState<string | null>(null)
  const quality = useQuery({
    queryKey: ["admin", "quality", filters] as const,
    queryFn: () => loadQuality(filters),
    placeholderData: (previous) => previous,
  })
  const inspection = useQuery({
    queryKey: ["admin", "conversation", openId] as const,
    queryFn: () => loadInspection(openId ?? ""),
    enabled: openId !== null,
    // Cada abertura é uma leitura auditada; não relê sozinha.
    staleTime: Infinity,
    gcTime: 0,
    retry: false,
  })

  async function reveal(id: string, reason: string): Promise<RevealResult> {
    try {
      const result = await api.POST("/v1/admin/conversations/{conversation_id}/reveal", {
        params: { path: { conversation_id: id } },
        body: { reason: reason.trim() },
      })
      if (!result.response.ok || !result.data) {
        return {
          ok: false,
          message: messageFrom(result.error, pt.couldNotContinue),
          fieldErrors: fieldErrorsFrom(result.error),
          requestId: requestIdFrom(result.error),
        }
      }
      return { ok: true, fullName: result.data.full_name, email: result.data.email }
    } catch {
      return { ok: false, message: pt.couldNotContinue, fieldErrors: {}, requestId: null }
    }
  }

  return {
    filters,
    setFilters,
    quality: quality.data,
    loading: quality.isPending,
    loadError: quality.isError,
    openId,
    open: setOpenId,
    inspection: inspection.data,
    inspectionLoading: inspection.isFetching,
    inspectionError: inspection.isError,
    reveal,
  }
}

export type QualityModel = ReturnType<typeof useQuality>
