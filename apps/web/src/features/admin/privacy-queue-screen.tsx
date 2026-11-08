/**
 * Fila de pedidos de titular do admin, em `/admin/privacy`: as contagens do
 * topo, a tabela com os atrasados primeiro e o `Sheet` de cada pedido, com
 * o formulário de status e nota.
 *
 * Camada: view (SDD 13.2). Recebe o `PrivacyQueueModel` de
 * `usePrivacyQueue` pela rota `app/routes/admin-privacy.tsx` e não chama a
 * API. Usa as regras de `privacy-queue-model.ts`, o `fill` e o
 * `formatDateTime` de `documents-model.ts`, o `DataTable`, o
 * `DueDateBadge`, o `StatTile` e o `RequestIdCopy` de
 * `components/patterns` e o `Sheet` de `components/ui`.
 *
 * SDD 15.5 (Pedidos de titular), 11.5 (prazo e nota de resolução), 12 e a
 * Jornada J8 (FR-16).
 */
import { useEffect, useRef, useState, type FormEvent } from "react"

import { PageHeading } from "@/app/page-heading.tsx"
import { DataTable, type DataTableColumn } from "@/components/patterns/data-table.tsx"
import { DueDateBadge, formatDate } from "@/components/patterns/due-date-badge.tsx"
import { RequestIdCopy } from "@/components/patterns/request-id-copy.tsx"
import { StatTile } from "@/components/patterns/stat-tile.tsx"
import { Badge } from "@/components/ui/badge.tsx"
import { Button } from "@/components/ui/button.tsx"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field.tsx"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet.tsx"
import { Skeleton } from "@/components/ui/skeleton.tsx"
import { Spinner } from "@/components/ui/spinner.tsx"
import { Textarea } from "@/components/ui/textarea.tsx"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group.tsx"
import { pt } from "@/i18n/pt.ts"

import { fill, formatDateTime } from "./documents-model.ts"
import {
  counts,
  isClosed,
  mailtoHref,
  needsNote,
  requestStatuses,
  resolutionNoteMaxChars,
  statusLabel,
  statusVariant,
  typeLabel,
  type PrivacyQueueItem,
  type RequestStatus,
} from "./privacy-queue-model.ts"
import type { PrivacyQueueModel } from "./usePrivacyQueue.ts"

const t = pt.privacyQueue
const d = pt.privacyQueue.detail

/** Badge do status. Um status desconhecido usa a superfície neutra. */
function StatusTag({ status }: { status: string }) {
  const variant = (statusVariant as Record<string, (typeof statusVariant)[RequestStatus]>)[status]
  return <Badge variant={variant ?? "secondary"}>{statusLabel(status)}</Badge>
}

/**
 * Fila de pedidos de titular: atrasados primeiro, com texto e não só cor.
 * SDD 15.5 (FR-16). A ordem vem pronta da API: os abertos e em andamento,
 * do prazo mais antigo ao mais novo, e depois os fechados.
 */
export function PrivacyQueueScreen(model: PrivacyQueueModel) {
  const data = model.queue
  // Os prazos contam a partir do `generated_at` da leitura, o instante que a
  // API usou no `overdue`: o selo e a contagem de atrasados concordam mesmo
  // com o relógio do navegador errado. Antes da primeira leitura, vale a
  // hora do navegador.
  const now = data?.generated_at ?? new Date().toISOString()
  // O pedido do `Sheet` sai da fila em cache, então cada releitura atualiza
  // o detalhe aberto.
  const selected = data?.requests.find((item) => item.id === model.openId) ?? null
  const summary = counts(data?.requests)

  // Colunas da seção 15.5: tipo (o cabeçalho da linha), contato, recebido
  // em, prazo, status e a ação de abrir.
  const columns: DataTableColumn<PrivacyQueueItem>[] = [
    {
      key: "type",
      header: t.table.type,
      rowHeader: true,
      cell: (row) => typeLabel(row.request_type),
    },
    {
      key: "contact",
      header: t.table.contact,
      cell: (row) => <span className="break-all">{row.contact_email}</span>,
    },
    {
      key: "received",
      header: t.table.receivedAt,
      cell: (row) => formatDateTime(row.received_at),
    },
    {
      key: "deadline",
      header: t.table.deadline,
      cell: (row) => <DueDateBadge dueAt={row.due_at} closedAt={row.closed_at} now={now} />,
    },
    {
      key: "status",
      header: t.table.status,
      cell: (row) => <StatusTag status={row.status} />,
    },
    {
      key: "actions",
      header: t.table.actions,
      cell: (row) => (
        // O nome acessível começa pelo texto visível e diz o tipo e o
        // contato do pedido, para distinguir as linhas (SDD 15.8).
        <Button
          size="sm"
          variant="outline"
          aria-label={`${t.table.open}: ${typeLabel(row.request_type)}, ${row.contact_email}`}
          onClick={() => {
            model.open(row.id)
          }}
        >
          {t.table.open}
        </Button>
      ),
    },
  ]

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <PageHeading title={pt.pages.privacyRequests} />
        <p className="text-body text-muted-foreground">{t.lead}</p>
      </header>

      {/* Atrasados (em `--danger` quando há algum), abertos e em andamento,
          acima da tabela (SDD 15.5). Com erro de leitura, nem o skeleton
          aparece: o alerta abaixo explica. */}
      {data ? (
        <section aria-label={t.summary.label} className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <StatTile
            label={t.summary.overdue}
            value={String(summary.overdue)}
            tone={summary.overdue > 0 ? "danger" : "neutral"}
          />
          <StatTile label={t.summary.open} value={String(summary.open)} />
          <StatTile label={t.summary.inProgress} value={String(summary.inProgress)} tone="info" />
        </section>
      ) : model.loadError ? null : (
        <Skeleton className="h-16 w-full" />
      )}

      {model.loadError ? (
        <p role="alert" className="text-body text-destructive">
          {t.table.loadFailed}
        </p>
      ) : (
        <DataTable
          caption={t.table.caption}
          columns={columns}
          rows={data?.requests}
          rowKey={(row) => row.id}
          loading={model.loading}
          empty={t.table.empty}
        />
      )}

      <RequestSheet
        request={selected}
        now={now}
        update={model.update}
        onClose={() => {
          model.open(null)
        }}
      />
    </div>
  )
}

// O aviso do detalhe, na região `aria-live`.
type Notice = { text: string; failed: boolean; requestId: string | null }

/**
 * O `Sheet` do pedido aberto. O `key` por id recria o detalhe ao trocar de
 * pedido, o que zera o formulário e o aviso. Sem pedido, o `Sheet` está
 * fechado; o cabeçalho genérico só garante que o conteúdo nunca fique sem
 * título (SDD 14.8).
 */
function RequestSheet({
  request,
  now,
  update,
  onClose,
}: {
  request: PrivacyQueueItem | null
  now: string
  update: PrivacyQueueModel["update"]
  onClose: () => void
}) {
  return (
    <Sheet
      open={request !== null}
      onOpenChange={(next) => {
        if (!next) {
          onClose()
        }
      }}
    >
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-xl">
        {request ? (
          <RequestDetail key={request.id} request={request} now={now} update={update} />
        ) : (
          <SheetHeader>
            <SheetTitle>{pt.pages.privacyRequests}</SheetTitle>
            <SheetDescription>{d.description}</SheetDescription>
          </SheetHeader>
        )}
      </SheetContent>
    </Sheet>
  )
}

/**
 * Detalhe de um pedido (SDD 15.5): o prazo, o status, o contato, as datas,
 * se o pedido veio com sessão de membro, o texto do pedido e o formulário
 * de status e nota. Um pedido fechado abre só para leitura, com a nota
 * gravada.
 */
function RequestDetail({
  request,
  now,
  update,
}: {
  request: PrivacyQueueItem
  now: string
  update: PrivacyQueueModel["update"]
}) {
  const [notice, setNotice] = useState<Notice | null>(null)
  const closed = isClosed(request.status)
  // O contato só vira link `mailto:` quando o endereço é seguro.
  const mailto = mailtoHref(request.contact_email)
  const closedHeading = useRef<HTMLHeadingElement>(null)
  // O estado da renderização anterior. O foco só muda na passagem de aberto
  // para fechado, e não ao abrir um pedido que já estava fechado.
  const wasClosed = useRef(closed)

  // Ao concluir ou recusar, o botão Salvar some: o foco vai para a nota
  // gravada (SDD 15.5). Uma releitura que traz o fechamento feito por outro
  // admin também move o foco.
  useEffect(() => {
    if (closed && !wasClosed.current) {
      closedHeading.current?.focus()
    }
    wasClosed.current = closed
  }, [closed])

  return (
    <>
      <SheetHeader>
        <SheetTitle>{fill(d.title, { type: typeLabel(request.request_type) })}</SheetTitle>
        <SheetDescription>{d.description}</SheetDescription>
      </SheetHeader>
      <div className="flex flex-col gap-5 px-4 pb-6">
        <div className="flex flex-wrap items-start gap-3">
          <DueDateBadge dueAt={request.due_at} closedAt={request.closed_at} now={now} />
          <StatusTag status={request.status} />
        </div>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-body">
          <dt className="text-muted-foreground">{d.contact}</dt>
          <dd className="break-all text-foreground">
            {mailto ? (
              <a href={mailto} className="underline underline-offset-4">
                {request.contact_email}
              </a>
            ) : (
              request.contact_email
            )}
          </dd>
          <dt className="text-muted-foreground">{d.receivedAt}</dt>
          <dd className="text-foreground">{formatDateTime(request.received_at)}</dd>
          {request.closed_at ? (
            <>
              <dt className="text-muted-foreground">{d.closedAt}</dt>
              <dd className="text-foreground">{formatDate(request.closed_at)}</dd>
            </>
          ) : null}
          <dt className="text-muted-foreground">{d.account}</dt>
          <dd className="text-foreground">{request.linked_account ? d.linked : d.notLinked}</dd>
        </dl>
        <section aria-labelledby="dsr-request-title" className="flex flex-col gap-2">
          <h3 id="dsr-request-title" className="text-label text-foreground-strong">
            {d.request}
          </h3>
          <p className="rounded-lg bg-muted px-3 py-2 text-body whitespace-pre-wrap text-foreground">
            {request.description}
          </p>
        </section>

        <div aria-live="polite" className="flex flex-col gap-2">
          {notice ? (
            <>
              <p
                role={notice.failed ? "alert" : "status"}
                className={notice.failed ? "text-body text-destructive" : "text-body text-foreground"}
              >
                {notice.text}
              </p>
              {notice.requestId ? <RequestIdCopy requestId={notice.requestId} /> : null}
            </>
          ) : null}
        </div>

        {/* Fechado, o pedido não muda mais e não tem formulário (SDD 11.5).
            `tabIndex={-1}` deixa o título receber o foco pelo código sem
            entrar na ordem do Tab. */}
        {closed ? (
          <section aria-labelledby="dsr-resolution-title" className="flex flex-col gap-2">
            <h3
              id="dsr-resolution-title"
              ref={closedHeading}
              tabIndex={-1}
              className="text-label text-foreground-strong"
            >
              {d.note}
            </h3>
            <p className="text-body whitespace-pre-wrap text-foreground">
              {request.resolution_note ?? d.noNote}
            </p>
            <p className="text-caption text-muted-foreground">{d.closedNotice}</p>
          </section>
        ) : (
          <UpdateForm request={request} update={update} onNotice={setNotice} />
        )}
      </div>
    </>
  )
}

/**
 * Formulário de status e nota de um pedido aberto (SDD 11.5 e 15.5).
 *
 * Segue as regras do servidor antes de chamar a API: concluir ou recusar
 * exige uma nota, nova ou já gravada, e a nota em branco mantém a gravada.
 * O estado vive enquanto o detalhe está aberto, então a releitura de 60
 * segundos não apaga o que o admin está digitando.
 */
function UpdateForm({
  request,
  update,
  onNotice,
}: {
  request: PrivacyQueueItem
  update: PrivacyQueueModel["update"]
  onNotice: (notice: Notice | null) => void
}) {
  // Um status fora da lista, que a API não deveria mandar, começa como
  // `open`.
  const initial = (requestStatuses as readonly string[]).includes(request.status)
    ? (request.status as RequestStatus)
    : "open"
  const [status, setStatus] = useState<RequestStatus>(initial)
  const [note, setNote] = useState(request.resolution_note ?? "")
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [pending, setPending] = useState(false)

  const storedNote = request.resolution_note ?? ""

  /** Confere a nota, envia a mudança e mostra o resultado. */
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    onNotice(null)
    // Mesma regra do servidor: nota em branco mantém a gravada, e fechar
    // exige alguma.
    if (needsNote(status) && note.trim() === "" && storedNote.trim() === "") {
      setErrors({ resolution_note: d.noteRequired })
      return
    }
    setErrors({})
    setPending(true)
    const result = await update(request.id, { status, resolutionNote: note })
    setPending(false)
    if (result.ok) {
      onNotice({
        text: fill(d.saved, { status: statusLabel(result.request.status) }),
        failed: false,
        requestId: null,
      })
      return
    }
    // Um erro de `status` ou de `resolution_note` vai para o campo. Os
    // outros, como o 409 de um pedido que outro admin fechou, vão para o
    // aviso com o `request_id`.
    setErrors(result.fieldErrors)
    if (Object.keys(result.fieldErrors).length === 0) {
      onNotice({ text: result.message, failed: true, requestId: result.requestId })
    }
  }

  const noteError = errors.resolution_note
  const statusError = errors.status

  return (
    <form noValidate className="flex flex-col gap-4" onSubmit={(event) => void submit(event)}>
      <FieldGroup>
        <Field data-invalid={statusError ? true : undefined}>
          <span id="dsr-status-label" className="text-label text-foreground">
            {d.statusLabel}
          </span>
          <ToggleGroup
            type="single"
            value={status}
            aria-labelledby="dsr-status-label"
            aria-describedby={statusError ? "dsr-status-error" : undefined}
            aria-invalid={statusError ? true : undefined}
            disabled={pending}
            // Clicar no status já marcado faz o Radix mandar `""`: só um
            // status da lista muda o estado. Trocar o status limpa os erros
            // e o aviso.
            onValueChange={(value) => {
              if ((requestStatuses as readonly string[]).includes(value)) {
                setStatus(value as RequestStatus)
                setErrors({})
                onNotice(null)
              }
            }}
          >
            {requestStatuses.map((value) => (
              <ToggleGroupItem key={value} value={value}>
                {statusLabel(value)}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          {statusError ? <FieldError id="dsr-status-error">{statusError}</FieldError> : null}
        </Field>
        <Field data-invalid={noteError ? true : undefined}>
          <FieldLabel htmlFor="dsr-note">{d.note}</FieldLabel>
          <Textarea
            id="dsr-note"
            value={note}
            maxLength={resolutionNoteMaxChars}
            disabled={pending}
            aria-invalid={noteError ? true : undefined}
            aria-describedby={noteError ? "dsr-note-hint dsr-note-error" : "dsr-note-hint"}
            // Digitar limpa o erro da nota e o aviso anterior.
            onChange={(event) => {
              setNote(event.target.value)
              if (noteError) {
                setErrors((current) => ({ ...current, resolution_note: "" }))
              }
              onNotice(null)
            }}
          />
          <FieldDescription id="dsr-note-hint">
            {storedNote ? `${d.noteHint} ${d.noteKeep}` : d.noteHint}
          </FieldDescription>
          {noteError ? <FieldError id="dsr-note-error">{noteError}</FieldError> : null}
        </Field>
      </FieldGroup>
      <Button type="submit" className="w-fit" disabled={pending}>
        {pending ? <Spinner aria-hidden="true" data-icon="inline-start" /> : null}
        {pending ? d.saving : d.save}
      </Button>
    </form>
  )
}
