/**
 * Modelo da gestão de documentos do admin: os tipos da resposta da API, o
 * limite e os tipos de arquivo aceitos, o status que a tabela mostra e duas
 * funções de texto. Só funções puras, sem React e sem rede.
 *
 * Quem usa: `useDocuments.ts` e `documents-screen.tsx`. O `formatDateTime`
 * e o `fill` também servem a `quality-screen.tsx` e a
 * `privacy-queue-screen.tsx`. Usa o `pt` de `i18n/pt.ts`.
 *
 * SDD 7.3 (ingestão), 12 (`/v1/admin/documents`) e 15.5 (Documentos).
 */
import { pt } from "@/i18n/pt.ts"

/**
 * Espelha `DocumentVersionResponse` do contrato (SDD 12). O
 * `ingestion_status` segue a ingestão da seção 7.3: começa em `processing`
 * e termina em `ready` ou em `failed`, com a mensagem em `error`.
 */
export type AdminDocumentVersion = {
  id: string
  version: number
  filename: string
  media_type: string
  byte_size: number
  ingestion_status: "processing" | "ready" | "failed"
  error: string | null
  created_at: string
}

/**
 * Espelha `DocumentResponse` do contrato (SDD 12). `active_version` é a
 * versão que responde às perguntas, e `latest_version` é a mais nova, que
 * pode estar em processamento ou ter falhado. As duas podem ser nulas:
 * logo depois do upload, ainda não há versão ativa.
 */
export type AdminDocument = {
  id: string
  title: string
  slug: string
  status: "active" | "archived"
  created_at: string
  updated_at: string
  active_version: AdminDocumentVersion | null
  latest_version: AdminDocumentVersion | null
}

/**
 * O limite de 10 MB e as extensões que o servidor aceita (SDD 7.3 e 12,
 * FR-10). O servidor decide pelo nome do arquivo, não pelo tipo que o
 * navegador declara. Aqui o navegador só adianta o aviso (NFR-10).
 */
export const maxUploadBytes = 10 * 1024 * 1024
export const acceptedExtensions = [".md", ".markdown", ".txt", ".pdf"] as const
/** Valor do atributo `accept`: o seletor de arquivos já filtra os tipos. */
export const acceptAttribute = acceptedExtensions.join(",")

/** O status de uma linha da tabela, derivado do documento e da versão. */
export type DisplayStatus = "processing" | "ready" | "failed" | "archived"

/**
 * Status de uma linha. Arquivado vence tudo. Fora isso, vale a última
 * versão: em processamento ou com falha. Sem nenhum dos dois, a linha está
 * pronta. Uma falha na versão nova mostra `failed` mesmo com a versão
 * ativa anterior ainda respondendo (FR-11).
 */
export function displayStatus(document: AdminDocument): DisplayStatus {
  if (document.status === "archived") {
    return "archived"
  }
  const latest = document.latest_version?.ingestion_status
  if (latest === "processing") {
    return "processing"
  }
  if (latest === "failed") {
    return "failed"
  }
  return "ready"
}

/**
 * Variante do `Badge` de cada status, com as cores da seção 15.5:
 * processando em `--info`, pronto em `--success`, falha em `--danger` e
 * arquivado na superfície neutra (`secondary`).
 */
export const statusVariant = {
  processing: "info",
  ready: "success",
  failed: "danger",
  archived: "secondary",
} as const

/**
 * Diz se alguma linha está em processamento. Enquanto houver uma, o
 * `useDocuments` relê a lista a cada 2 segundos (SDD 15.5).
 */
export function isProcessing(documents: AdminDocument[] | undefined) {
  return (documents ?? []).some((item) => displayStatus(item) === "processing")
}

/**
 * Confere o arquivo no navegador antes do envio: obrigatório, com extensão
 * aceita (sem diferenciar maiúsculas) e com até 10 MB.
 *
 * @returns A mensagem do problema, ou `null` quando o arquivo pode seguir.
 *   Arquivo vazio, texto que não é UTF-8 e PDF que não começa com `%PDF-`
 *   só o servidor recusa, com `field_errors.file` (SDD 12).
 */
export function fileProblem(file: File | null): string | null {
  if (!file) {
    return pt.documents.dropzone.required
  }
  const name = file.name.toLowerCase()
  if (!acceptedExtensions.some((extension) => name.endsWith(extension))) {
    return pt.documents.dropzone.wrongType
  }
  if (file.size > maxUploadBytes) {
    return pt.documents.dropzone.tooLarge
  }
  return null
}

/** Data e hora curtas em português, no fuso do navegador. */
export function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

/**
 * Troca cada `{chave}` do texto pelo valor, em todas as ocorrências. Por
 * exemplo, `fill("v{version}", { version: 2 })` dá `"v2"`.
 */
export function fill(template: string, values: Record<string, string | number>) {
  return Object.entries(values).reduce(
    (text, [key, value]) => text.replaceAll(`{${key}}`, String(value)),
    template,
  )
}
