import { useQuery } from "@tanstack/react-query"

import { queryClient } from "@/app/query-client.ts"
import {
  fieldErrorsFrom,
  messageFrom,
  requestIdFrom,
} from "@/features/auth/api-error.ts"
import { pt } from "@/i18n/pt.ts"
import { api } from "@/lib/api/client.ts"

import { isProcessing, type AdminDocument } from "./documents-model.ts"

/** Enquanto houver versão em processamento, a lista é relida a cada 2 segundos. */
export const processingRefetchMs = 2000

export const documentsQuery = {
  queryKey: ["admin", "documents"] as const,
  queryFn: loadDocuments,
}

export type ActionFailure = {
  ok: false
  message: string
  fieldErrors: Record<string, string>
  requestId: string | null
}

export type ActionResult = { ok: true; document: AdminDocument } | ActionFailure

async function loadDocuments(): Promise<AdminDocument[]> {
  const result = await api.GET("/v1/admin/documents")
  if (!result.response.ok || !result.data) {
    throw new Error(messageFrom(result.error, pt.documents.table.loadFailed))
  }
  return result.data.documents
}

function failure(error: unknown): ActionFailure {
  return {
    ok: false,
    message: messageFrom(error, pt.couldNotContinue),
    fieldErrors: fieldErrorsFrom(error),
    requestId: requestIdFrom(error),
  }
}

const networkFailure: ActionFailure = {
  ok: false,
  message: pt.couldNotContinue,
  fieldErrors: {},
  requestId: null,
}

function formData(fields: Record<string, string | Blob | null | undefined>) {
  const data = new FormData()
  for (const [key, value] of Object.entries(fields)) {
    if (value instanceof File) {
      data.append(key, value, value.name)
    } else if (value != null && value !== "") {
      data.append(key, value)
    }
  }
  return data
}

async function settle(
  call: Promise<{ data?: AdminDocument; error?: unknown; response: Response }>,
): Promise<ActionResult> {
  try {
    const result = await call
    if (!result.response.ok || !result.data) {
      return failure(result.error)
    }
    await queryClient.invalidateQueries({ queryKey: documentsQuery.queryKey })
    return { ok: true, document: result.data }
  } catch {
    return networkFailure
  }
}

export function useDocuments() {
  const documents = useQuery({
    ...documentsQuery,
    refetchInterval: (query) =>
      isProcessing(query.state.data) ? processingRefetchMs : false,
  })

  function upload(file: File, title: string) {
    return settle(
      api.POST("/v1/admin/documents", {
        body: { file: "", title },
        bodySerializer: () => formData({ file, title: title.trim() }),
      }),
    )
  }

  function replace(documentId: string, file: File) {
    return settle(
      api.POST("/v1/admin/documents/{document_id}/replace", {
        params: { path: { document_id: documentId } },
        body: { file: "" },
        bodySerializer: () => formData({ file }),
      }),
    )
  }

  function retry(documentId: string) {
    return settle(
      api.POST("/v1/admin/documents/{document_id}/retry", {
        params: { path: { document_id: documentId } },
      }),
    )
  }

  function archive(documentId: string) {
    return settle(
      api.POST("/v1/admin/documents/{document_id}/archive", {
        params: { path: { document_id: documentId } },
      }),
    )
  }

  return {
    documents: documents.data,
    loading: documents.isPending,
    loadError: documents.isError,
    upload,
    replace,
    retry,
    archive,
  }
}

export type DocumentsModel = ReturnType<typeof useDocuments>
