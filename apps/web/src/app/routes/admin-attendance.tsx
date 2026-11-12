/**
 * Rota `/admin/attendance`, os atendimentos encerrados (seção 29.11, J11).
 *
 * Liga o controller `useClosedHandoffs` à tela `ClosedScreen` (SDD 13.2). O
 * guard `requireAdmin` barra quem não é admin, inclusive o `attendant`.
 */
import { ClosedScreen } from "@/features/attendance/closed-screen.tsx"
import { useClosedHandoffs } from "@/features/attendance/useClosedHandoffs.ts"

/** Passa a lista e a ação de abrir para a tela. */
export function Component() {
  const closed = useClosedHandoffs()
  return (
    <ClosedScreen
      period={closed.period}
      onPeriod={closed.setPeriod}
      rows={closed.rows}
      loading={closed.loading}
      error={closed.error}
      onView={closed.view}
    />
  )
}
