/**
 * A oferta do atendimento humano, abaixo da resposta que não ajudou
 * (seções 29.4 e 29.11).
 *
 * Aparece na conversa (`features/ask/conversation-screen.tsx`) só nos
 * desfechos da seção 29.4, que `offerAnswer` escolhe. Com a disponibilidade
 * `open`, a pergunta e o botão Falar com uma pessoa. Com `busy` ou `closed`,
 * o texto com a mesa telefônica no lugar do botão. Com `disabled`, ou sem a
 * leitura da disponibilidade, nada. O bloqueio por abuso mostra o aviso da
 * seção 29.11.
 */
import { Headset } from "lucide-react"

import { Button } from "@/components/ui/button.tsx"
import { pt } from "@/i18n/pt.ts"

/** Disponibilidade da seção 29.4, como `GET /v1/handoff/availability`. */
export type HandoffAvailability = "open" | "busy" | "closed" | "disabled"

/** A oferta, ou o motivo de não haver oferta agora. */
export function HandoffOffer({
  availability,
  blocked = false,
  pending = false,
  onRequest,
}: {
  availability: HandoffAvailability | null
  /** Encerramento por abuso nas últimas 24 horas (seção 29.4). */
  blocked?: boolean
  /** O pedido saiu e ainda não voltou. */
  pending?: boolean
  /** Abre o `HandoffDialog`. O pedido só sai depois da confirmação. */
  onRequest: () => void
}) {
  if (availability === null || availability === "disabled") {
    return null
  }
  if (blocked) {
    return (
      <p className="text-body text-muted-foreground">{pt.handoff.blocked}</p>
    )
  }
  if (availability !== "open") {
    return (
      <p className="text-body text-muted-foreground">
        {availability === "busy" ? pt.handoff.busy : pt.handoff.closed}
      </p>
    )
  }
  return (
    <div className="flex flex-col items-start gap-3 rounded-xl bg-card px-4 py-3 ring-1 ring-foreground/10 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-body text-foreground">{pt.handoff.offerQuestion}</p>
      <Button
        type="button"
        variant="secondary"
        className="min-h-11 md:min-h-8"
        disabled={pending}
        onClick={onRequest}
      >
        <Headset aria-hidden="true" data-icon="inline-start" />
        {pt.handoff.offerButton}
      </Button>
    </div>
  )
}
