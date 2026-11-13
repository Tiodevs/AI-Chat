/**
 * A fila do atendimento humano no console da equipe, sem conteúdo (seções
 * 29.9.4 e 29.11).
 *
 * Cada item tem o rótulo do atendimento ("Visitante" e 8 caracteres do HMAC
 * do id), a espera relativa, o motivo da oferta e as marcas Devolvido e
 * Visitante ausente. Nunca o texto da conversa, nome, e-mail ou tipo de
 * visitante: a fila não recebe esses dados da API. Assumir sobe por
 * `onTake`; com 3 atendimentos, o botão fica desabilitado e o motivo
 * aparece acima da lista.
 *
 * O atendimento que veio do WhatsApp tem o selo WhatsApp, com o ícone
 * `MessageCircle`: só o canal, nunca o número (seção 30.11).
 *
 * Movimento: um item novo entra com `autoAlpha` e `y` de 8 a 0
 * (`enterQueueItem`), direto com movimento reduzido.
 */
import { MessageCircle } from "lucide-react"
import { useRef } from "react"

import { Badge } from "@/components/ui/badge.tsx"
import { Button } from "@/components/ui/button.tsx"
import { Spinner } from "@/components/ui/spinner.tsx"
import { pt } from "@/i18n/pt.ts"
import { useGSAP } from "@/motion/gsap.ts"
import { useMotion } from "@/motion/MotionProvider.tsx"
import { presets } from "@/motion/presets.ts"

/** Um item da fila, como o evento `queue` e `GET /v1/attendance/queue`. */
export type QueueItemView = {
  handoffId: string
  label: string
  queuedAt: string
  trigger: string
  returned: boolean
  visitorPresent: boolean
  /** `whatsapp` mostra o selo do canal (seção 30.11). */
  channel?: "web" | "whatsapp"
}

/** A espera desde `queuedAt`, em minutos, como "Esperando há 3 minutos". */
export function waitText(queuedAt: string, now: Date): string {
  const minutes = Math.floor((now.getTime() - Date.parse(queuedAt)) / 60_000)
  const time =
    minutes < 1
      ? pt.attendance.justNow
      : minutes === 1
        ? pt.attendance.minutesOne
        : pt.attendance.minutesMany.replace("{minutes}", String(minutes))
  return pt.attendance.waiting.replace("{time}", time)
}

/** O rótulo do motivo da oferta (seção 29.11). */
export function triggerText(trigger: string): string {
  const labels: Record<string, string> = pt.attendance.triggers
  return labels[trigger] ?? trigger
}

/** A lista da fila, com o vazio. */
export function QueueList({
  items,
  now,
  canTake,
  pendingId = null,
  onTake,
}: {
  items: QueueItemView[]
  /** A hora de referência da espera, que a tela troca a cada 15 segundos. */
  now: Date
  /** Falso com 3 atendimentos ou como Ausente. */
  canTake: boolean
  /** O atendimento que está sendo assumido. */
  pendingId?: string | null
  onTake: (handoffId: string) => void
}) {
  if (items.length === 0) {
    return (
      <p className="text-body text-muted-foreground">
        {pt.attendance.emptyQueue}
      </p>
    )
  }
  return (
    <ol
      aria-label={pt.attendance.queueLabel}
      className="m-0 flex list-none flex-col gap-2 p-0"
    >
      {items.map((item) => (
        <QueueRow
          key={item.handoffId}
          item={item}
          now={now}
          canTake={canTake && pendingId === null}
          pending={pendingId === item.handoffId}
          onTake={onTake}
        />
      ))}
    </ol>
  )
}

/** Um item da fila, que entra com o preset ao montar. */
function QueueRow({
  item,
  now,
  canTake,
  pending,
  onTake,
}: {
  item: QueueItemView
  now: Date
  canTake: boolean
  pending: boolean
  onTake: (handoffId: string) => void
}) {
  const ref = useRef<HTMLLIElement>(null)
  const { reduced } = useMotion()
  useGSAP(
    () => {
      presets.enterQueueItem(ref.current, reduced)
    },
    { scope: ref }
  )
  return (
    <li
      ref={ref}
      className="flex flex-col gap-3 rounded-xl bg-card px-4 py-3 ring-1 ring-foreground/10 sm:flex-row sm:items-center sm:justify-between"
    >
      <div className="flex min-w-0 flex-col gap-1.5">
        <span className="font-mono text-label text-foreground-strong">
          {item.label}
        </span>
        <span className="text-caption text-muted-foreground">
          {waitText(item.queuedAt, now)}
        </span>
        <div className="flex flex-wrap gap-1.5">
          {item.channel === "whatsapp" ? (
            <Badge variant="outline">
              <MessageCircle aria-hidden="true" />
              {pt.attendance.whatsapp}
            </Badge>
          ) : null}
          <Badge variant="secondary">{triggerText(item.trigger)}</Badge>
          {item.returned ? (
            <Badge variant="outline">{pt.attendance.returned}</Badge>
          ) : null}
          {item.visitorPresent ? null : (
            <Badge variant="outline">{pt.attendance.visitorAway}</Badge>
          )}
        </div>
      </div>
      <Button
        type="button"
        className="min-h-11 md:min-h-8"
        disabled={!canTake || pending}
        aria-label={`${pt.attendance.take} ${item.label}`}
        onClick={() => {
          onTake(item.handoffId)
        }}
      >
        {pending ? (
          <Spinner aria-hidden="true" data-icon="inline-start" />
        ) : null}
        {pending ? pt.attendance.taking : pt.attendance.take}
      </Button>
    </li>
  )
}
