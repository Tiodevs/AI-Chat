/**
 * Tela `/attendance`: a fila e os atendimentos da pessoa da equipe. Seções
 * 29.3, 29.5 e 29.11 do SDD (J10).
 *
 * View: recebe de `app/routes/attendance.tsx` o retrato e as ações de
 * `useAttendance` e não chama a API. No topo, o `PresenceToggle` e três
 * `StatTile`: Na fila, Comigo e Equipe disponível. À esquerda, a `QueueList`
 * sem conteúdo; à direita, até 3 atendimentos em `Tabs`, cada um com o
 * `HandoffThread`, o compositor, a orientação de emergência, Devolver à
 * fila e Encerrar com o motivo num `Select` e a confirmação num
 * `AlertDialog`.
 *
 * O título da aba só leva a contagem de novidades, como "(2) Atendimento ·
 * Atrium", e nunca conteúdo (seção 29.9.4). A espera da fila é recalculada
 * a cada 15 segundos.
 */
import { MessageCircle } from "lucide-react"
import { useEffect, useState } from "react"

import { PageHeading } from "@/app/page-heading.tsx"
import { Composer } from "@/components/patterns/composer.tsx"
import { HandoffThread } from "@/components/patterns/handoff-thread.tsx"
import { PresenceToggle } from "@/components/patterns/presence-toggle.tsx"
import { QueueList, triggerText } from "@/components/patterns/queue-list.tsx"
import { RedactDialog } from "@/components/patterns/redact-dialog.tsx"
import { StatTile } from "@/components/patterns/stat-tile.tsx"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog.tsx"
import { Badge } from "@/components/ui/badge.tsx"
import { Button } from "@/components/ui/button.tsx"
import { Field, FieldLabel } from "@/components/ui/field.tsx"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select.tsx"
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs.tsx"
import { pt } from "@/i18n/pt.ts"

import { consoleTitle, type DetailView } from "./model.ts"
import type {
  ConsoleSnapshot,
  TakeResult,
  useAttendance,
} from "./useAttendance.ts"

/** O máximo de atendimentos de uma pessoa (seção 29.14). */
const maxPerAttendant = 3
/** A espera da fila é recalculada a cada 15 segundos (seção 29.11). */
const clockEveryMs = 15_000

type Console = ReturnType<typeof useAttendance>

/** A tela do console. */
export function AttendanceScreen({
  console: view,
  onTake,
}: {
  console: Console
  /** Assume e, sem o compromisso, leva a `/attendance/commitment`. */
  onTake: (handoffId: string) => Promise<TakeResult>
}) {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = window.setInterval(() => {
      setNow(new Date())
    }, clockEveryMs)
    return () => {
      window.clearInterval(timer)
    }
  }, [])

  const unread = Object.values(view.unread).reduce(
    (total, value) => total + value,
    0
  )
  const count = view.queue.length + unread
  useEffect(() => {
    // Roda depois do `PageHeading`, que grava o título da página.
    document.title = consoleTitle(count)
  }, [count])

  const atCapacity = view.mine.length >= maxPerAttendant
  const away = view.presence === "away"

  return (
    <div className="mx-auto flex w-full max-w-[1100px] flex-col gap-6">
      <PageHeading title={pt.pages.attendance} />
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <PresenceToggle
          value={view.presence}
          pending={view.busy}
          onChange={(status) => {
            void view.setPresence(status)
          }}
        />
        <div className="grid grid-cols-3 gap-2">
          <StatTile
            label={pt.attendance.stats.queued}
            value={String(view.queue.length)}
          />
          <StatTile
            label={pt.attendance.stats.mine}
            value={String(view.mine.length)}
          />
          <StatTile
            label={pt.attendance.stats.available}
            value={String(view.availableAttendants)}
          />
        </div>
      </div>
      <div role="status" className="flex flex-col gap-2">
        {away ? (
          <p className="text-body text-foreground">
            {pt.attendance.awayNotice}
          </p>
        ) : null}
        {view.connection === "reconnecting" ? (
          <p className="text-caption text-muted-foreground">
            {pt.attendance.reconnecting}
          </p>
        ) : null}
        {view.notice ? (
          <p className="text-body text-foreground">{view.notice}</p>
        ) : null}
      </div>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)]">
        <section aria-labelledby="queue-title" className="flex flex-col gap-3">
          <h2 id="queue-title" className="text-title text-foreground-strong">
            {pt.attendance.queueTitle}
          </h2>
          {atCapacity ? (
            <p className="text-caption text-muted-foreground">
              {pt.attendance.atCapacity}
            </p>
          ) : null}
          <QueueList
            items={view.queue}
            now={now}
            canTake={!atCapacity}
            pendingId={view.takingId}
            onTake={(handoffId) => {
              void onTake(handoffId)
            }}
          />
        </section>
        <section
          aria-labelledby="handoffs-title"
          className="flex flex-col gap-3"
        >
          <h2 id="handoffs-title" className="text-title text-foreground-strong">
            {pt.attendance.handoffsLabel}
          </h2>
          {view.mine.length === 0 ? (
            <p className="text-body text-muted-foreground">
              {pt.attendance.noHandoffs}
            </p>
          ) : (
            <Tabs
              value={view.selected ?? view.mine[0] ?? ""}
              onValueChange={(next) => {
                view.select(next)
              }}
            >
              <TabsList>
                {view.mine.map((handoffId) => (
                  <TabsTrigger key={handoffId} value={handoffId}>
                    {view.details[handoffId]?.handoff.label ?? pt.loading}
                    {view.unread[handoffId] ? (
                      <Badge variant="secondary">
                        {view.unread[handoffId]}
                      </Badge>
                    ) : null}
                  </TabsTrigger>
                ))}
              </TabsList>
              {view.mine.map((handoffId) => (
                <TabsContent key={handoffId} value={handoffId}>
                  <HandoffPanel
                    handoffId={handoffId}
                    detail={view.details[handoffId]}
                    view={view}
                  />
                </TabsContent>
              ))}
            </Tabs>
          )}
        </section>
      </div>
    </div>
  )
}

/** Um atendimento aberto: a conversa, o compositor e as ações. */
function HandoffPanel({
  handoffId,
  detail,
  view,
}: {
  handoffId: string
  detail: DetailView | undefined
  view: Console & ConsoleSnapshot
}) {
  const [value, setValue] = useState("")
  const [redacting, setRedacting] = useState<string | null>(null)
  const [closing, setClosing] = useState(false)
  const [reason, setReason] = useState("")

  if (!detail) {
    return <p className="text-body text-muted-foreground">{pt.loading}</p>
  }
  const reasons = Object.entries(pt.attendance.closeReasons)
  return (
    <div className="flex flex-col gap-4 pt-3">
      <div className="flex flex-wrap items-center gap-2">
        {detail.handoff.channel === "whatsapp" ? (
          <Badge variant="outline">
            <MessageCircle aria-hidden="true" />
            {pt.attendance.whatsapp}
          </Badge>
        ) : null}
        <Badge variant="secondary">{triggerText(detail.handoff.trigger)}</Badge>
        <Badge variant="outline">
          {detail.handoff.visitorPresent
            ? pt.attendance.visitorPresent
            : pt.attendance.visitorAway}
        </Badge>
      </div>
      <HandoffThread
        conversation={detail.conversation}
        messages={detail.messages}
        onRedact={(messageId) => {
          setRedacting(messageId)
        }}
      />
      <Composer
        value={value}
        onChange={setValue}
        onSubmit={() => {
          const text = value.trim()
          if (!text) {
            return
          }
          void view.send(handoffId, text).then((sent) => {
            if (sent) {
              setValue("")
            }
          })
        }}
        onStop={() => undefined}
        streaming={false}
        pending={view.busy}
        disabled={false}
        disabledReason={null}
        error={null}
        label={pt.attendance.composerLabel}
        placeholder={pt.attendance.placeholder}
        hint={
          detail.handoff.channel === "whatsapp"
            ? pt.attendance.whatsappComposer
            : pt.attendance.composerHint
        }
        maxLength={2000}
      />
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="secondary"
          disabled={view.busy}
          onClick={() => {
            void view.sendEmergency(handoffId)
          }}
        >
          {pt.attendance.emergency}
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={view.busy}
          onClick={() => {
            void view.release(handoffId)
          }}
        >
          {pt.attendance.release}
        </Button>
        <Button
          type="button"
          variant="destructive"
          disabled={view.busy}
          onClick={() => {
            setClosing(true)
          }}
        >
          {pt.attendance.close}
        </Button>
      </div>
      <RedactDialog
        open={redacting !== null}
        pending={view.busy}
        onOpenChange={(open) => {
          if (!open) {
            setRedacting(null)
          }
        }}
        onConfirm={(category) => {
          if (redacting) {
            void view.redact(handoffId, redacting, category).then(() => {
              setRedacting(null)
            })
          }
        }}
      />
      <AlertDialog
        open={closing}
        onOpenChange={(open) => {
          setClosing(open)
          if (!open) {
            setReason("")
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{pt.attendance.closeTitle}</AlertDialogTitle>
            <AlertDialogDescription>
              {pt.attendance.closeDescription}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <Field>
            <FieldLabel htmlFor={`close-reason-${handoffId}`}>
              {pt.attendance.closeReasonLabel}
            </FieldLabel>
            <Select value={reason} onValueChange={setReason}>
              <SelectTrigger id={`close-reason-${handoffId}`}>
                <SelectValue
                  placeholder={pt.attendance.closeReasonPlaceholder}
                />
              </SelectTrigger>
              <SelectContent>
                {reasons.map(([key, label]) => (
                  <SelectItem key={key} value={key}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <AlertDialogFooter>
            <AlertDialogCancel>{pt.attendance.cancel}</AlertDialogCancel>
            <AlertDialogAction
              disabled={!reason || view.busy}
              onClick={(event) => {
                // O Radix fecha no clique; o fechamento espera o pedido.
                event.preventDefault()
                void view.close(handoffId, reason).then(() => {
                  setClosing(false)
                  setReason("")
                })
              }}
            >
              {pt.attendance.closeConfirm}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
