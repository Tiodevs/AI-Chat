/**
 * Controlador da fila de pedidos de titular do admin (`/admin/privacy`): lê
 * a fila, relê a cada minuto e muda o status e a nota de um pedido.
 *
 * Camada: controller (SDD 13.2). Quem usa: `app/routes/admin-privacy.tsx`,
 * que entrega o retorno a `PrivacyQueueScreen`. Usa o cliente `api`, o
 * `queryClient`, os leitores de erro de `features/auth/api-error.ts` e os
 * tipos de `privacy-queue-model.ts`.
 *
 * Cada mudança de status ou de nota grava `dsr.update` no servidor, com a
 * troca de status no motivo e sem a nota nem o e-mail. SDD 11.5, 12 e 15.5
 * (Pedidos de titular), Jornada J8.
 */
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

/** Consulta da fila, `GET /v1/admin/privacy/requests`. */
export const privacyQueueQuery = {
  queryKey: ["admin", "privacy-requests"] as const,
  queryFn: loadQueue,
}

/**
 * Relê a fila a cada minuto: um prazo pode vencer com a tela aberta e
 * mudar de estado (SDD 15.5, FR-16). Com a aba em segundo plano, o TanStack
 * Query pausa esse intervalo.
 */
export const queueRefetchMs = 60_000

/** Resultado de uma mudança: o pedido como a API o devolveu, ou a falha. */
export type UpdateResult =
  | { ok: true; request: PrivacyQueueItem }
  | {
      ok: false
      message: string
      fieldErrors: Record<string, string>
      requestId: string | null
    }

// Lança na falha, para o `useQuery` marcar `isError` e a tela mostrar o
// aviso no lugar da tabela.
async function loadQueue(): Promise<PrivacyQueue> {
  const result = await api.GET("/v1/admin/privacy/requests")
  if (!result.response.ok || !result.data) {
    throw new Error(messageFrom(result.error, pt.privacyQueue.table.loadFailed))
  }
  return result.data
}

/**
 * Fila de pedidos de titular do admin. SDD 11.5, 12 e 15.5.
 *
 * @returns A fila (`undefined` enquanto carrega), os estados `loading` e
 *   `loadError`, o pedido aberto no `Sheet` (`openId` e `open`) e `update`,
 *   que nunca lança.
 */
export function usePrivacyQueue() {
  const queue = useQuery({ ...privacyQueueQuery, refetchInterval: queueRefetchMs })
  const [openId, setOpenId] = useState<string | null>(null)

  /**
   * Muda o status e a nota de um pedido, com
   * `PATCH /v1/admin/privacy/requests/{id}` (SDD 12).
   *
   * 1. Tira os espaços das pontas da nota. Nota vazia vai como `null`, e o
   *    servidor mantém a nota gravada.
   * 2. Envia `{ status, resolution_note }`.
   * 3. Com sucesso ou com falha, invalida a fila. Na falha, a releitura
   *    traz o estado real: outro admin pode ter fechado o pedido (409).
   * 4. Devolve o pedido atualizado ou a falha, com os erros de campo e o
   *    `request_id`.
   */
  async function update(
    id: string,
    change: { status: RequestStatus; resolutionNote: string },
  ): Promise<UpdateResult> {
    try {
      // 1.
      const note = change.resolutionNote.trim()
      // 2.
      const result = await api.PATCH("/v1/admin/privacy/requests/{request_id}", {
        params: { path: { request_id: id } },
        // Nota vazia mantém a nota atual no servidor.
        body: { status: change.status, resolution_note: note === "" ? null : note },
      })
      if (!result.response.ok || !result.data) {
        // 3. Outro admin pode ter fechado o pedido (409): relê para o
        // detalhe não ficar velho.
        await queryClient.invalidateQueries({ queryKey: privacyQueueQuery.queryKey })
        // 4.
        return {
          ok: false,
          message: messageFrom(result.error, pt.couldNotContinue),
          fieldErrors: fieldErrorsFrom(result.error),
          requestId: requestIdFrom(result.error),
        }
      }
      // 3. e 4. O `await` espera a releitura: quando `update` termina, a fila
      // já mostra o status novo, e o detalhe aberto acompanha.
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

/** O que `PrivacyQueueScreen` recebe: o retorno de `usePrivacyQueue`. */
export type PrivacyQueueModel = ReturnType<typeof usePrivacyQueue>
