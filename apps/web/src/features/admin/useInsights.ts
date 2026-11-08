/**
 * Controladores da visão geral (`/admin`) e da qualidade (`/admin/quality`):
 * leem os indicadores, a lista de conversas e o inspetor, e revelam a
 * identidade de um membro com um motivo.
 *
 * Camada: controller (SDD 13.2). Quem usa: `app/routes/admin.tsx`, com o
 * `useOverview`, e `app/routes/admin-quality.tsx`, com o `useQuality`. Usa
 * o cliente `api`, os leitores de erro de `features/auth/api-error.ts` e os
 * tipos de `insights-model.ts`.
 *
 * Privacidade: a lista e o inspetor só trazem pseudônimos. Abrir uma
 * conversa grava `conversation.view`, e revelar a identidade grava
 * `identity.reveal` com o motivo (SDD 11.8 e 12). SDD 15.5 (Visão geral e
 * Qualidade).
 */
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

/** Filtros da qualidade. `null` em `outcome` ou `feedback` quer dizer todos. */
export type QualityFilters = {
  period: Period
  outcome: string | null
  feedback: string | null
}

/** Resultado da revelação: nome e e-mail, ou a falha com os erros de campo. */
export type RevealResult =
  | { ok: true; fullName: string; email: string }
  | { ok: false; message: string; fieldErrors: Record<string, string>; requestId: string | null }

// As três leituras lançam na falha, para o `useQuery` marcar `isError` e a
// tela mostrar o aviso.

/** Indicadores do período, `GET /v1/admin/overview?period_days=...`. */
async function loadOverview(period: Period): Promise<Overview> {
  const result = await api.GET("/v1/admin/overview", {
    params: { query: { period_days: period } },
  })
  if (!result.response.ok || !result.data) {
    throw new Error(messageFrom(result.error, pt.insights.loadFailed))
  }
  return result.data
}

/**
 * Contagens e conversas do período, `GET /v1/admin/quality`. Um filtro
 * `undefined` sai da URL, e a API não filtra por ele.
 */
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

/**
 * A conversa do inspetor, `GET /v1/admin/conversations/{id}`. Cada chamada
 * grava `conversation.view` na mesma transação da leitura. Uma conversa de
 * membro sem `quality_improvement` vigente responde 404 (SDD 12).
 */
async function loadInspection(id: string): Promise<Inspection> {
  const result = await api.GET("/v1/admin/conversations/{conversation_id}", {
    params: { path: { conversation_id: id } },
  })
  if (!result.response.ok || !result.data) {
    throw new Error(messageFrom(result.error, pt.quality.inspector.loadFailed))
  }
  return result.data
}

/**
 * Indicadores da visão geral (SDD 15.5).
 *
 * O período, 7 ou 30 dias, vale para a tela toda e entra na chave da
 * consulta, então cada período tem a sua entrada no cache. O
 * `placeholderData` devolve os dados do período anterior enquanto o novo
 * carrega: a tela troca os números sem voltar aos skeletons.
 */
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

/** O que `OverviewScreen` recebe: o retorno de `useOverview`. */
export type OverviewModel = ReturnType<typeof useOverview>

/**
 * Lista, filtros, inspetor e revelação da tela de qualidade (SDD 15.5 e
 * Jornada J7).
 *
 * 1. Os filtros entram na chave da lista. Trocar um filtro pede
 *    `GET /v1/admin/quality` de novo, com os dados anteriores na tela até
 *    a resposta.
 * 2. `openId` abre o inspetor. A consulta da conversa só roda com um id.
 * 3. `reveal` pede a identidade sem passar pelo cache.
 */
export function useQuality() {
  // 1.
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
  // 2. Cada abertura é uma leitura auditada, então a consulta não relê
  // sozinha: `staleTime: Infinity` nunca a dá por velha, e `retry: false`
  // não repete uma falha. `gcTime: 0` tira a conversa do cache quando o
  // inspetor fecha; abrir de novo lê de novo e grava outro
  // `conversation.view`.
  const inspection = useQuery({
    queryKey: ["admin", "conversation", openId] as const,
    queryFn: () => loadInspection(openId ?? ""),
    enabled: openId !== null,
    staleTime: Infinity,
    gcTime: 0,
    retry: false,
  })

  /**
   * 3. Revela nome e e-mail do membro dono da conversa, com
   * `POST /v1/admin/conversations/{id}/reveal` e o motivo (SDD 11.8 e 12).
   * A API grava `identity.reveal` com o motivo, responde 409 numa conversa
   * de convidado e 404 numa conversa fora do inspetor. A identidade não
   * entra no cache do TanStack Query: só o formulário que pediu a guarda.
   */
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
    // `isFetching`, e não `isPending`: uma consulta desligada, sem id, também
    // fica `pending`, sem estar lendo nada.
    inspectionLoading: inspection.isFetching,
    inspectionError: inspection.isError,
    reveal,
  }
}

/** O que `QualityScreen` recebe: o retorno de `useQuality`. */
export type QualityModel = ReturnType<typeof useQuality>
