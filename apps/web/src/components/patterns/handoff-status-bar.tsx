/**
 * A barra do atendimento humano acima do compositor: posição na fila ou
 * atendimento em curso, e o botão de sair (seções 29.5 e 29.11).
 *
 * Aparece na conversa enquanto o atendimento está na fila ou com a equipe.
 * A mudança de estado vai para uma região `role="status"`, que o leitor de
 * tela anuncia sem tirar o foco do compositor (seção 29.11). "Reconectando…"
 * aparece discreto quando o fluxo caiu há mais de 5 segundos.
 *
 * Movimento: ao mudar de estado, `autoAlpha` e `y` de 8 a 0 em
 * `duration.base` (`enterHandoffStatus`), direto com movimento reduzido.
 */
import { useRef } from "react"

import { Button } from "@/components/ui/button.tsx"
import { Spinner } from "@/components/ui/spinner.tsx"
import { pt } from "@/i18n/pt.ts"
import { useGSAP } from "@/motion/gsap.ts"
import { useMotion } from "@/motion/MotionProvider.tsx"
import { presets } from "@/motion/presets.ts"

/** A barra do atendimento na fila ou em curso. */
export function HandoffStatusBar({
  status,
  queuePosition,
  returned = false,
  reconnecting = false,
  pending = false,
  onEnd,
}: {
  status: "queued" | "assigned"
  queuePosition: number | null
  /** Voltou para a fila depois de alguém assumir (seção 29.5, passo 6). */
  returned?: boolean
  reconnecting?: boolean
  /** O encerramento saiu e ainda não voltou. */
  pending?: boolean
  /** Sai da fila ou encerra o atendimento (FR-24). */
  onEnd: () => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  const { reduced } = useMotion()
  useGSAP(
    () => {
      presets.enterHandoffStatus(ref.current, reduced)
    },
    { scope: ref, dependencies: [status] }
  )
  const queued = status === "queued"
  const text = queued
    ? pt.handoff.queued.replace("{position}", String(queuePosition ?? 1))
    : pt.handoff.assigned
  return (
    <div
      ref={ref}
      className="flex flex-col gap-2 rounded-xl bg-card px-4 py-3 ring-1 ring-foreground/10 sm:flex-row sm:items-center sm:justify-between"
    >
      <div role="status" className="flex flex-col gap-1">
        {queued && returned ? (
          <p className="text-body text-foreground">{pt.handoff.returned}</p>
        ) : null}
        <p className="text-body text-foreground-strong">{text}</p>
        {reconnecting ? (
          <p className="text-caption text-muted-foreground">
            {pt.handoff.reconnecting}
          </p>
        ) : null}
      </div>
      <Button
        type="button"
        variant="outline"
        className="min-h-11 md:min-h-8"
        disabled={pending}
        onClick={onEnd}
      >
        {pending ? (
          <Spinner aria-hidden="true" data-icon="inline-start" />
        ) : null}
        {queued ? pt.handoff.leaveQueue : pt.handoff.end}
      </Button>
    </div>
  )
}
