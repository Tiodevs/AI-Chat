/**
 * Rota `/admin`, a visão geral do admin: indicadores, gráfico de perguntas,
 * desfechos, funil de cadastro e orçamento de tokens (seção 15.5).
 *
 * Liga o controller `useOverview`, de `features/admin/useInsights.ts`, à
 * tela `OverviewScreen` (SDD 13.2). O guard `requireAdmin` barra quem não
 * é admin.
 */
import { OverviewScreen } from "@/features/admin/overview-screen.tsx"
import { useOverview } from "@/features/admin/useInsights.ts"

/** Passa o modelo do controller inteiro para a tela. */
export function Component() {
  const model = useOverview()
  return <OverviewScreen {...model} />
}
