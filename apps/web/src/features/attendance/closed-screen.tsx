/**
 * Tela `/admin/attendance`: os atendimentos encerrados, para o admin
 * apurar uma reclamação (seção 29.11, J11).
 *
 * View: recebe de `app/routes/admin-attendance.tsx` a lista e a ação de
 * abrir. A `DataTable` mostra rótulo, motivo da oferta, espera, duração,
 * motivo de encerramento e se o texto já foi apagado, sem conteúdo. Abrir
 * pede o motivo num `Dialog`, de 10 a 500 caracteres, antes de chamar a
 * API, e mostra a conversa num `Sheet` só de leitura (FR-26).
 */
import { useState, type FormEvent } from "react"

import { PageHeading } from "@/app/page-heading.tsx"
import { DataTable } from "@/components/patterns/data-table.tsx"
import { HandoffThread } from "@/components/patterns/handoff-thread.tsx"
import { triggerText } from "@/components/patterns/queue-list.tsx"
import { Badge } from "@/components/ui/badge.tsx"
import { Button } from "@/components/ui/button.tsx"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog.tsx"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@/components/ui/field.tsx"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet.tsx"
import { Spinner } from "@/components/ui/spinner.tsx"
import { Textarea } from "@/components/ui/textarea.tsx"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group.tsx"
import { pt } from "@/i18n/pt.ts"

import { minutesBetween, type DetailView } from "./model.ts"
import type { ClosedRow, ViewResult } from "./useClosedHandoffs.ts"

/** O motivo do admin, depois de juntar os espaços, como a API confere. */
function reasonIsValid(reason: string) {
  const value = reason.split(/\s+/).filter(Boolean).join(" ")
  return value.length >= 10 && value.length <= 500
}

/** O rótulo do motivo de encerramento. */
function closeLabel(reason: string | null) {
  const labels: Record<string, string> = pt.adminAttendance.closeReasons
  return reason ? (labels[reason] ?? reason) : "—"
}

/** A tela dos encerrados. */
export function ClosedScreen({
  period,
  onPeriod,
  rows,
  loading,
  error,
  onView,
}: {
  period: 7 | 30
  onPeriod: (period: 7 | 30) => void
  rows: ClosedRow[] | undefined
  loading: boolean
  error: string | null
  onView: (handoffId: string, reason: string) => Promise<ViewResult>
}) {
  const [target, setTarget] = useState<ClosedRow | null>(null)
  const [opened, setOpened] = useState<{
    row: ClosedRow
    detail: DetailView
  } | null>(null)
  const t = pt.adminAttendance
  return (
    <div className="mx-auto flex w-full max-w-[1100px] flex-col gap-6">
      <PageHeading title={pt.pages.adminAttendance} />
      <p className="text-body text-muted-foreground">{t.description}</p>
      <ToggleGroup
        type="single"
        value={String(period)}
        aria-label={t.periodLabel}
        onValueChange={(next) => {
          if (next === "7" || next === "30") {
            onPeriod(next === "7" ? 7 : 30)
          }
        }}
      >
        <ToggleGroupItem value="7">{t.period7}</ToggleGroupItem>
        <ToggleGroupItem value="30">{t.period30}</ToggleGroupItem>
      </ToggleGroup>
      {error ? (
        <p role="alert" className="text-body text-danger">
          {error}
        </p>
      ) : (
        <DataTable
          caption={pt.pages.adminAttendance}
          rows={rows}
          loading={loading}
          rowKey={(row) => row.id}
          empty={t.empty}
          columns={[
            {
              key: "label",
              header: t.columns.label,
              rowHeader: true,
              cell: (row) => <span className="font-mono">{row.label}</span>,
            },
            {
              key: "trigger",
              header: t.columns.trigger,
              cell: (row) => triggerText(row.trigger),
            },
            {
              key: "wait",
              header: t.columns.wait,
              cell: (row) => minutesBetween(row.requestedAt, row.assignedAt),
            },
            {
              key: "duration",
              header: t.columns.duration,
              cell: (row) => minutesBetween(row.requestedAt, row.closedAt),
            },
            {
              key: "close",
              header: t.columns.closeReason,
              cell: (row) => closeLabel(row.closeReason),
            },
            {
              key: "purged",
              header: t.columns.purged,
              cell: (row) => (
                <Badge variant="outline">
                  {row.contentPurged ? t.purgedYes : t.purgedNo}
                </Badge>
              ),
            },
            {
              key: "actions",
              header: t.columns.actions,
              cell: (row) => (
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  aria-label={`${t.open} ${row.label}`}
                  onClick={() => {
                    setTarget(row)
                  }}
                >
                  {t.open}
                </Button>
              ),
            },
          ]}
        />
      )}
      <ReasonDialog
        row={target}
        onClose={() => {
          setTarget(null)
        }}
        onView={onView}
        onOpened={(row, detail) => {
          setTarget(null)
          setOpened({ row, detail })
        }}
      />
      <Sheet
        open={opened !== null}
        onOpenChange={(open) => {
          if (!open) {
            setOpened(null)
          }
        }}
      >
        <SheetContent className="flex w-full flex-col gap-4 overflow-y-auto sm:max-w-xl">
          <SheetHeader>
            <SheetTitle>
              {t.sheetTitle.replace("{label}", opened?.row.label ?? "")}
            </SheetTitle>
            <SheetDescription>{t.sheetDescription}</SheetDescription>
          </SheetHeader>
          {opened ? (
            <div className="px-4 pb-6">
              <HandoffThread
                conversation={opened.detail.conversation}
                messages={opened.detail.messages}
                readOnly
              />
            </div>
          ) : null}
        </SheetContent>
      </Sheet>
    </div>
  )
}

/** O motivo antes de abrir um encerrado. */
function ReasonDialog({
  row,
  onClose,
  onView,
  onOpened,
}: {
  row: ClosedRow | null
  onClose: () => void
  onView: (handoffId: string, reason: string) => Promise<ViewResult>
  onOpened: (row: ClosedRow, detail: DetailView) => void
}) {
  const [reason, setReason] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const t = pt.adminAttendance

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!row) {
      return
    }
    // O motivo é conferido antes de chamar a API (seção 29.11).
    if (!reasonIsValid(reason)) {
      setError(t.reasonError)
      return
    }
    setPending(true)
    const result = await onView(row.id, reason)
    setPending(false)
    if (result.ok) {
      setReason("")
      setError(null)
      onOpened(row, result.detail)
      return
    }
    setError(result.reasonError ?? result.message)
  }

  return (
    <Dialog
      open={row !== null}
      onOpenChange={(open) => {
        if (!open) {
          setError(null)
          onClose()
        }
      }}
    >
      <DialogContent>
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(event) => void submit(event)}
        >
          <DialogHeader>
            <DialogTitle>{t.reasonTitle}</DialogTitle>
            <DialogDescription>{row?.label ?? ""}</DialogDescription>
          </DialogHeader>
          <Field data-invalid={error ? true : undefined}>
            <FieldLabel htmlFor="view-reason">{t.reasonLabel}</FieldLabel>
            <Textarea
              id="view-reason"
              value={reason}
              maxLength={500}
              disabled={pending}
              aria-invalid={error ? true : undefined}
              aria-describedby={
                error
                  ? "view-reason-hint view-reason-error"
                  : "view-reason-hint"
              }
              onChange={(event) => {
                setReason(event.target.value)
              }}
            />
            <FieldDescription id="view-reason-hint">
              {t.reasonHint}
            </FieldDescription>
            {error ? (
              <FieldError id="view-reason-error">{error}</FieldError>
            ) : null}
          </Field>
          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              disabled={pending}
              onClick={onClose}
            >
              {pt.attendance.cancel}
            </Button>
            <Button type="submit" disabled={pending}>
              {pending ? (
                <Spinner aria-hidden="true" data-icon="inline-start" />
              ) : null}
              {pending ? t.opening : t.confirm}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
