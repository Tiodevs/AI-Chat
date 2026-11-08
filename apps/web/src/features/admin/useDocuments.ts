/**
 * Controlador da gestão de documentos do admin (`/admin/documents`): lê a
 * lista e envia, substitui, tenta de novo e arquiva documentos.
 *
 * Camada: controller (SDD 13.2). Quem usa: `app/routes/admin-documents.tsx`,
 * que entrega o retorno a `DocumentsScreen`. Usa o cliente `api`, o
 * `queryClient`, os leitores de erro de `features/auth/api-error.ts` e as
 * regras de `documents-model.ts`.
 *
 * As ações respondem logo: a ingestão roda numa tarefa de fundo da API,
 * depois da resposta (SDD 7.3), e a tela acompanha pela releitura da lista.
 * SDD 10.4 (limite de uploads), 12 e 15.5 (Documentos).
 */
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

/**
 * Enquanto houver versão em processamento, a lista é relida a cada 2
 * segundos (SDD 15.5).
 */
export const processingRefetchMs = 2000

/**
 * Consulta da lista, `GET /v1/admin/documents`: os ativos primeiro e depois
 * os arquivados, do mais recente ao mais antigo (SDD 12).
 */
export const documentsQuery = {
  queryKey: ["admin", "documents"] as const,
  queryFn: loadDocuments,
}

/** Falha de uma ação: a mensagem, os erros de campo e o `request_id`. */
export type ActionFailure = {
  ok: false
  message: string
  fieldErrors: Record<string, string>
  requestId: string | null
}

/** Resultado de uma ação: o documento devolvido pela API, ou a falha. */
export type ActionResult = { ok: true; document: AdminDocument } | ActionFailure

// Lança na falha, para o `useQuery` marcar `isError` e a tela mostrar o
// aviso no lugar da tabela.
async function loadDocuments(): Promise<AdminDocument[]> {
  const result = await api.GET("/v1/admin/documents")
  if (!result.response.ok || !result.data) {
    throw new Error(messageFrom(result.error, pt.documents.table.loadFailed))
  }
  return result.data.documents
}

/** Lê o corpo de erro da seção 12. Sem `message`, vale a cópia genérica. */
function failure(error: unknown): ActionFailure {
  return {
    ok: false,
    message: messageFrom(error, pt.couldNotContinue),
    fieldErrors: fieldErrorsFrom(error),
    requestId: requestIdFrom(error),
  }
}

/** Falha sem resposta HTTP, como a rede fora do ar. */
const networkFailure: ActionFailure = {
  ok: false,
  message: pt.couldNotContinue,
  fieldErrors: {},
  requestId: null,
}

/**
 * Monta o corpo `multipart/form-data` do upload. Um `File` vai com o nome
 * original, porque a API tira dele o tipo, pela extensão, e o `slug`.
 * Texto vazio ou nulo fica de fora: sem título, a API usa o nome do
 * arquivo sem a extensão (SDD 12).
 */
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

/**
 * Espera uma ação e a traduz para `ActionResult`. No sucesso, invalida a
 * lista: a releitura traz a versão nova e, com ela em `processing`, liga a
 * releitura a cada 2 segundos. O `await` deixa a tabela atualizada antes de
 * a tela anunciar o resultado.
 */
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

/**
 * Lista e ações da tela de documentos.
 *
 * Substituir ou tentar de novo responde 409 num documento arquivado ou com
 * uma versão em processamento há menos de 15 minutos. Enviar, substituir e
 * tentar de novo contam no balde de uploads, e o 31º pedido da hora
 * responde 429 (SDD 10.4 e 12). A falha leva a mensagem do servidor.
 *
 * @returns A lista (`undefined` enquanto carrega), os estados `loading` e
 *   `loadError` e as ações `upload`, `replace`, `retry` e `archive`, que
 *   devolvem `ActionResult` e nunca lançam.
 */
export function useDocuments() {
  // `refetchInterval` aceita uma função, que o TanStack Query chama depois
  // de cada leitura: 2 segundos enquanto houver processamento, `false`
  // (sem releitura) quando não houver.
  const documents = useQuery({
    ...documentsQuery,
    refetchInterval: (query) =>
      isProcessing(query.state.data) ? processingRefetchMs : false,
  })

  /**
   * Envia um documento novo, `POST /v1/admin/documents`, com `file` e o
   * `title` opcional. A API responde 201 com a versão em `processing` e
   * grava `document.upload`.
   */
  function upload(file: File, title: string) {
    return settle(
      // O tipo gerado do OpenAPI pede um `body` com `file` em texto. Esse
      // `body` só satisfaz o tipo e faz o `openapi-fetch` chamar o
      // `bodySerializer`, que devolve o `FormData` de verdade. Com
      // `FormData`, o `openapi-fetch` não põe `Content-Type`, e o navegador
      // define o `multipart/form-data` com o separador.
      api.POST("/v1/admin/documents", {
        body: { file: "", title },
        bodySerializer: () => formData({ file, title: title.trim() }),
      }),
    )
  }

  /**
   * Envia uma versão nova, `POST /v1/admin/documents/{id}/replace`, só com
   * `file`. Responde 202. A versão ativa continua respondendo até a nova
   * chegar a `ready` (FR-11). Grava `document.replace`.
   */
  function replace(documentId: string, file: File) {
    return settle(
      api.POST("/v1/admin/documents/{document_id}/replace", {
        params: { path: { document_id: documentId } },
        body: { file: "" },
        bodySerializer: () => formData({ file }),
      }),
    )
  }

  /**
   * Reprocessa o arquivo da última versão, que precisa estar em `failed`,
   * numa versão nova: `POST /v1/admin/documents/{id}/retry`, sem corpo.
   * Responde 202 e grava `document.retry`.
   */
  function retry(documentId: string) {
    return settle(
      api.POST("/v1/admin/documents/{document_id}/retry", {
        params: { path: { document_id: documentId } },
      }),
    )
  }

  /**
   * Arquiva o documento, `POST /v1/admin/documents/{id}/archive`: ele sai
   * das respostas do assistente na hora (FR-12). Grava `document.archive`.
   */
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

/** O que `DocumentsScreen` recebe: o retorno de `useDocuments`. */
export type DocumentsModel = ReturnType<typeof useDocuments>
