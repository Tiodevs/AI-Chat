/**
 * Rota `/attendance/commitment`, o compromisso de confidencialidade da
 * equipe (seção 29.3).
 *
 * Liga o controller `useAttendance`, sem abrir o fluxo do console, à tela
 * `CommitmentScreen`. Depois do aceite, volta para `/attendance`.
 */
import { useNavigate } from "react-router"

import { pt } from "@/i18n/pt.ts"
import { CommitmentScreen } from "@/features/attendance/commitment-screen.tsx"
import { useAttendance } from "@/features/attendance/useAttendance.ts"

/** Grava o aceite e volta ao console. */
export function Component() {
  const navigate = useNavigate()
  const attendance = useAttendance({ stream: false })
  return (
    <CommitmentScreen
      version={attendance.termsVersion}
      pending={attendance.busy}
      error={
        attendance.notice === pt.attendance.actionFailed
          ? attendance.notice
          : null
      }
      onAccept={() => {
        void attendance.acknowledge().then(async (accepted) => {
          if (accepted) {
            await navigate("/attendance")
          }
        })
      }}
    />
  )
}
