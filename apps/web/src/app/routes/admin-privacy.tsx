/**
 * Rota `/admin/privacy`, a fila de pedidos de titular com os prazos
 * (seção 15.5).
 *
 * Liga o controller `usePrivacyQueue` à tela `PrivacyQueueScreen` (SDD
 * 13.2). O guard `requireAdmin` barra quem não é admin.
 */
import { PrivacyQueueScreen } from "@/features/admin/privacy-queue-screen.tsx"
import { usePrivacyQueue } from "@/features/admin/usePrivacyQueue.ts"

/** Passa o modelo do controller inteiro para a tela. */
export function Component() {
  const model = usePrivacyQueue()
  return <PrivacyQueueScreen {...model} />
}
