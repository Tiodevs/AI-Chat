/**
 * Remover o conteúdo de uma mensagem do atendimento, com a categoria
 * (seções 29.9.6 e 29.11).
 *
 * A categoria vem de um `ToggleGroup` de escolha única, que o Radix expõe
 * como `radiogroup`. O texto é apagado na hora, sem cópia, e a auditoria
 * guarda só a categoria. Remover sobe por `onConfirm` para o
 * `useAttendance`.
 */
import { useId, useState } from "react"

import { Button } from "@/components/ui/button.tsx"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog.tsx"
import { Spinner } from "@/components/ui/spinner.tsx"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group.tsx"
import { pt } from "@/i18n/pt.ts"

/** As cinco categorias que a equipe escolhe (seção 29.10). */
export const redactCategories = [
  "health",
  "document",
  "contact",
  "third_party",
  "other",
] as const

export type RedactCategory = (typeof redactCategories)[number]

/** O diálogo de remoção. */
export function RedactDialog({
  open,
  onOpenChange,
  onConfirm,
  pending = false,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: (category: RedactCategory) => void
  pending?: boolean
}) {
  const [category, setCategory] = useState<RedactCategory>("health")
  const labelId = useId()
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{pt.attendance.redactTitle}</DialogTitle>
          <DialogDescription>
            {pt.attendance.redactDescription}
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-2">
          <span id={labelId} className="text-label text-foreground">
            {pt.attendance.redactCategory}
          </span>
          <ToggleGroup
            type="single"
            value={category}
            aria-labelledby={labelId}
            onValueChange={(next) => {
              const found = redactCategories.find((item) => item === next)
              if (found) {
                setCategory(found)
              }
            }}
          >
            {redactCategories.map((item) => (
              <ToggleGroupItem key={item} value={item}>
                {pt.attendance.categories[item]}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </div>
        <DialogFooter>
          <Button
            type="button"
            variant="ghost"
            disabled={pending}
            onClick={() => {
              onOpenChange(false)
            }}
          >
            {pt.attendance.cancel}
          </Button>
          <Button
            type="button"
            variant="destructive"
            disabled={pending}
            onClick={() => {
              onConfirm(category)
            }}
          >
            {pending ? (
              <Spinner aria-hidden="true" data-icon="inline-start" />
            ) : null}
            {pt.attendance.redactConfirm}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
