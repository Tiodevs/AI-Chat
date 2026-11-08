/**
 * Rota `/admin/quality`: desfechos, feedback e as conversas
 * pseudonimizadas, com o inspetor (seção 15.5).
 *
 * Liga o controller `useQuality`, de `features/admin/useInsights.ts`, à
 * tela `QualityScreen` (SDD 13.2). O guard `requireAdmin` barra quem não é
 * admin.
 */
import { QualityScreen } from "@/features/admin/quality-screen.tsx"
import { useQuality } from "@/features/admin/useInsights.ts"

/** Passa o modelo do controller inteiro para a tela. */
export function Component() {
  const model = useQuality()
  return <QualityScreen {...model} />
}
