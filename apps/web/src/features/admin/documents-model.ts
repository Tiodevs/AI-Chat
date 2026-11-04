import { pt } from "@/i18n/pt.ts"

/** Espelha `DocumentVersionResponse` do contrato (SDD 12). */
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

/** Espelha `DocumentResponse` do contrato (SDD 12). */
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

/** Limite e tipos do servidor (SDD 7.3, FR-10). O servidor decide; aqui só adianta o aviso. */
export const maxUploadBytes = 10 * 1024 * 1024
export const acceptedExtensions = [".md", ".markdown", ".txt", ".pdf"] as const
export const acceptAttribute = acceptedExtensions.join(",")

export type DisplayStatus = "processing" | "ready" | "failed" | "archived"

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

export const statusVariant = {
  processing: "info",
  ready: "success",
  failed: "danger",
  archived: "secondary",
} as const

export function isProcessing(documents: AdminDocument[] | undefined) {
  return (documents ?? []).some((item) => displayStatus(item) === "processing")
}

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

export function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

export function fill(template: string, values: Record<string, string | number>) {
  return Object.entries(values).reduce(
    (text, [key, value]) => text.replaceAll(`{${key}}`, String(value)),
    template,
  )
}
