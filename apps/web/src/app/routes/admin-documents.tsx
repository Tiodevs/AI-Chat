import { DocumentsScreen } from "@/features/admin/documents-screen.tsx"
import { useDocuments } from "@/features/admin/useDocuments.ts"

export function Component() {
  const model = useDocuments()
  return <DocumentsScreen {...model} />
}
