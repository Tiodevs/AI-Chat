/**
 * Rota `/admin/documents`: enviar, substituir, tentar de novo e arquivar
 * os documentos do corpus (seção 15.5).
 *
 * Liga o controller `useDocuments` à tela `DocumentsScreen` (SDD 13.2). O
 * guard `requireAdmin` barra quem não é admin.
 */
import { DocumentsScreen } from "@/features/admin/documents-screen.tsx"
import { useDocuments } from "@/features/admin/useDocuments.ts"

/** Passa o modelo do controller inteiro para a tela. */
export function Component() {
  const model = useDocuments()
  return <DocumentsScreen {...model} />
}
