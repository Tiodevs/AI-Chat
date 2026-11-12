/**
 * Disponível ou Ausente, no topo do console de atendimento (seção 29.11).
 *
 * Um `ToggleGroup` de escolha única, que o Radix expõe como `radiogroup`.
 * Disponível, com o console aberto, conta a pessoa como presente: a
 * disponibilidade do visitante passa a `open` (seção 29.4). A troca sobe
 * por `onChange` para o `useAttendance`.
 */
import { useId } from "react"

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group.tsx"
import { pt } from "@/i18n/pt.ts"

/** O status de presença da seção 29.7. */
export type PresenceValue = "available" | "away"

/** O seletor de presença. */
export function PresenceToggle({
  value,
  onChange,
  pending = false,
}: {
  value: PresenceValue
  onChange: (value: PresenceValue) => void
  /** A troca saiu e ainda não voltou. */
  pending?: boolean
}) {
  const labelId = useId()
  return (
    <div className="flex flex-col gap-2">
      <span id={labelId} className="text-label text-foreground">
        {pt.attendance.presenceLabel}
      </span>
      <ToggleGroup
        type="single"
        value={value}
        aria-labelledby={labelId}
        disabled={pending}
        onValueChange={(next) => {
          // O Radix manda vazio quando a pessoa clica no item já ligado.
          if (next === "available" || next === "away") {
            onChange(next)
          }
        }}
      >
        <ToggleGroupItem value="available">
          {pt.attendance.available}
        </ToggleGroupItem>
        <ToggleGroupItem value="away">{pt.attendance.away}</ToggleGroupItem>
      </ToggleGroup>
    </div>
  )
}
