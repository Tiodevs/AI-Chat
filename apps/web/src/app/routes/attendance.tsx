/**
 * Rota `/attendance`, a fila e os atendimentos da equipe (seção 29.11).
 *
 * Liga o controller `useAttendance` à tela `AttendanceScreen` (SDD 13.2). O
 * guard `requireStaff` barra quem não é `attendant` nem `admin`. Sem o aceite
 * do compromisso vigente, Assumir leva a `/attendance/commitment` (seção
 * 29.3).
 */
import { useNavigate } from "react-router"

import { AttendanceScreen } from "@/features/attendance/attendance-screen.tsx"
import { useAttendance } from "@/features/attendance/useAttendance.ts"

/** Passa o console à tela e trata o compromisso que falta. */
export function Component() {
  const navigate = useNavigate()
  const attendance = useAttendance()
  return (
    <AttendanceScreen
      console={attendance}
      onTake={async (handoffId) => {
        const result = await attendance.take(handoffId)
        if (result === "commitment") {
          await navigate("/attendance/commitment")
        }
        return result
      }}
    />
  )
}
