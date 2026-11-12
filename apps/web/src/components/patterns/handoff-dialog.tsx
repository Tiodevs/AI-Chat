/**
 * Confirmação antes de chamar a equipe, com o texto da seção 29.9.5.
 *
 * Diz o que a equipe vai ler, o que não vai para a IA e por quanto tempo o
 * texto fica guardado: transparência no momento da coleta (LGPD, art. 6º,
 * VI). Agora não fecha sem chamar a API, e Chamar a equipe sobe por
 * `onConfirm` para o `useHandoff` (FR-20). O título é o do `Dialog`, então
 * o leitor de tela o anuncia ao abrir.
 */
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
import { pt } from "@/i18n/pt.ts"

/** O diálogo de confirmação do atendimento humano. */
export function HandoffDialog({
  open,
  onOpenChange,
  onConfirm,
  pending,
  error,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Chama a equipe. Só aqui o pedido sai (FR-20). */
  onConfirm: () => void
  pending: boolean
  /** Falha do pedido, já em português. */
  error: string | null
}) {
  const t = pt.handoff.dialog
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t.title}</DialogTitle>
          <DialogDescription>{t.intro}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3 text-body text-foreground">
          <p>{t.notShared}</p>
          <p>{t.noHealth}</p>
          <p>{t.retention}</p>
        </div>
        {error ? (
          <p role="alert" className="text-body text-danger">
            {error}
          </p>
        ) : null}
        <DialogFooter>
          <Button
            type="button"
            variant="ghost"
            disabled={pending}
            onClick={() => {
              onOpenChange(false)
            }}
          >
            {t.cancel}
          </Button>
          <Button type="button" disabled={pending} onClick={onConfirm}>
            {pending ? (
              <Spinner aria-hidden="true" data-icon="inline-start" />
            ) : null}
            {pending ? t.calling : t.confirm}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
