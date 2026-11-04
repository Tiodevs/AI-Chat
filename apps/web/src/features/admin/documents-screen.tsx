import { useState, type FormEvent } from "react"

import { PageHeading } from "@/app/page-heading.tsx"
import { DataTable, type DataTableColumn } from "@/components/patterns/data-table.tsx"
import { FileDropzone } from "@/components/patterns/file-dropzone.tsx"
import { RequestIdCopy } from "@/components/patterns/request-id-copy.tsx"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog.tsx"
import { Badge } from "@/components/ui/badge.tsx"
import { Button } from "@/components/ui/button.tsx"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card.tsx"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field.tsx"
import { Input } from "@/components/ui/input.tsx"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet.tsx"
import { Spinner } from "@/components/ui/spinner.tsx"
import { pt } from "@/i18n/pt.ts"

import {
  acceptAttribute,
  displayStatus,
  fileProblem,
  fill,
  formatDateTime,
  statusVariant,
  type AdminDocument,
} from "./documents-model.ts"
import type { ActionFailure, ActionResult, DocumentsModel } from "./useDocuments.ts"

type Notice = { text: string; requestId: string | null; failed: boolean }

const t = pt.documents

export function DocumentsScreen(model: DocumentsModel) {
  const [notice, setNotice] = useState<Notice | null>(null)
  const [replacing, setReplacing] = useState<AdminDocument | null>(null)

  function announce(text: string) {
    setNotice({ text, requestId: null, failed: false })
  }

  function report(result: ActionFailure) {
    setNotice({ text: result.message, requestId: result.requestId, failed: true })
  }

  const columns: DataTableColumn<AdminDocument>[] = [
    {
      key: "title",
      header: t.table.title,
      rowHeader: true,
      cell: (document) => <TitleCell document={document} />,
    },
    {
      key: "active",
      header: t.table.activeVersion,
      cell: (document) =>
        document.active_version
          ? fill(t.table.version, { version: document.active_version.version })
          : t.table.noActive,
    },
    {
      key: "status",
      header: t.table.status,
      cell: (document) => {
        const status = displayStatus(document)
        return (
          <Badge variant={statusVariant[status]}>
            {status === "processing" ? <Spinner aria-hidden="true" /> : null}
            {t.status[status]}
          </Badge>
        )
      },
    },
    {
      key: "updated",
      header: t.table.updatedAt,
      cell: (document) => formatDateTime(document.updated_at),
    },
    {
      key: "actions",
      header: t.table.actions,
      cell: (document) => (
        <RowActions
          document={document}
          model={model}
          onReplace={() => {
            setReplacing(document)
          }}
          onDone={announce}
          onFailure={report}
        />
      ),
    },
  ]

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <PageHeading title={pt.pages.documents} />
        <p className="text-body text-muted-foreground">{t.lead}</p>
      </header>

      <UploadCard
        upload={model.upload}
        onDone={announce}
        onFailure={(result) => {
          if (Object.keys(result.fieldErrors).length === 0) {
            report(result)
          }
        }}
      />

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

      {model.loadError ? (
        <p role="alert" className="text-body text-destructive">
          {t.table.loadFailed}
        </p>
      ) : (
        <DataTable
          caption={t.table.caption}
          columns={columns}
          rows={model.documents}
          rowKey={(document) => document.id}
          loading={model.loading}
          empty={t.table.empty}
        />
      )}

      <ReplaceSheet
        document={replacing}
        replace={model.replace}
        onClose={() => {
          setReplacing(null)
        }}
        onDone={announce}
      />
    </div>
  )
}

function TitleCell({ document }: { document: AdminDocument }) {
  const latest = document.latest_version
  const status = displayStatus(document)
  return (
    <div className="flex flex-col gap-1">
      <span>{document.title}</span>
      <span className="font-mono text-caption font-normal text-muted-foreground">
        {document.slug}
      </span>
      {status === "processing" && latest && document.active_version ? (
        <span className="text-caption font-normal text-muted-foreground">
          {fill(t.processingNote, { version: latest.version })}
        </span>
      ) : null}
      {status === "failed" && latest ? (
        <span className="text-caption font-normal text-destructive">
          {fill(t.failedNote, { version: latest.version, error: latest.error ?? "" })}
        </span>
      ) : null}
    </div>
  )
}

function RowActions({
  document,
  model,
  onReplace,
  onDone,
  onFailure,
}: {
  document: AdminDocument
  model: DocumentsModel
  onReplace: () => void
  onDone: (text: string) => void
  onFailure: (result: ActionFailure) => void
}) {
  const [pending, setPending] = useState<"retry" | "archive" | null>(null)
  const [confirming, setConfirming] = useState(false)
  const status = displayStatus(document)

  if (status === "archived") {
    return null
  }

  async function run(kind: "retry" | "archive", done: string) {
    setPending(kind)
    const result: ActionResult =
      kind === "retry" ? await model.retry(document.id) : await model.archive(document.id)
    setPending(null)
    setConfirming(false)
    if (result.ok) {
      onDone(fill(done, { title: document.title }))
    } else {
      onFailure(result)
    }
  }

  const label = (action: string) => `${action}: ${document.title}`

  return (
    <div className="flex flex-wrap gap-2">
      {status === "failed" ? (
        <Button
          size="sm"
          variant="outline"
          disabled={pending !== null}
          aria-label={label(t.actions.retry)}
          onClick={() => {
            void run("retry", t.actions.retried)
          }}
        >
          {pending === "retry" ? <Spinner aria-hidden="true" data-icon="inline-start" /> : null}
          {pending === "retry" ? t.actions.retrying : t.actions.retry}
        </Button>
      ) : null}
      <Button
        size="sm"
        variant="outline"
        disabled={pending !== null || status === "processing"}
        aria-label={label(t.actions.replace)}
        onClick={onReplace}
      >
        {t.actions.replace}
      </Button>
      <AlertDialog open={confirming} onOpenChange={setConfirming}>
        <AlertDialogTrigger asChild>
          <Button
            size="sm"
            variant="ghost"
            disabled={pending !== null}
            aria-label={label(t.actions.archive)}
          >
            {t.actions.archive}
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{fill(t.actions.archiveTitle, { title: document.title })}</AlertDialogTitle>
            <AlertDialogDescription>{t.actions.archiveBody}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={pending !== null}>{t.actions.cancel}</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={pending !== null}
              onClick={(event) => {
                event.preventDefault()
                void run("archive", t.actions.archived)
              }}
            >
              {pending === "archive" ? <Spinner aria-hidden="true" data-icon="inline-start" /> : null}
              {t.actions.archiveConfirm}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function UploadCard({
  upload,
  onDone,
  onFailure,
}: {
  upload: DocumentsModel["upload"]
  onDone: (text: string) => void
  onFailure: (result: ActionFailure) => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState("")
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [pending, setPending] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const problem = fileProblem(file)
    if (problem || !file) {
      setErrors({ file: problem ?? t.dropzone.required })
      return
    }
    setPending(true)
    const result = await upload(file, title)
    setPending(false)
    if (result.ok) {
      setFile(null)
      setTitle("")
      setErrors({})
      onDone(fill(t.upload.sent, { title: result.document.title }))
      return
    }
    setErrors(result.fieldErrors)
    onFailure(result)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2 className="text-label text-foreground-strong">{t.upload.title}</h2>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form noValidate onSubmit={(event) => void submit(event)}>
          <FieldGroup>
            <FileDropzone
              file={file}
              accept={acceptAttribute}
              error={errors.file}
              disabled={pending}
              onFileChange={(next) => {
                setFile(next)
                setErrors((current) => ({ ...current, file: next ? (fileProblem(next) ?? "") : "" }))
              }}
            />
            <Field data-invalid={errors.title ? true : undefined}>
              <FieldLabel htmlFor="document-title">{t.upload.titleLabel}</FieldLabel>
              <Input
                id="document-title"
                value={title}
                maxLength={200}
                disabled={pending}
                aria-invalid={errors.title ? true : undefined}
                aria-describedby={errors.title ? "document-title-hint document-title-error" : "document-title-hint"}
                onChange={(event) => {
                  setTitle(event.target.value)
                }}
              />
              <FieldDescription id="document-title-hint">{t.upload.titleHint}</FieldDescription>
              {errors.title ? <FieldError id="document-title-error">{errors.title}</FieldError> : null}
            </Field>
            <div>
              <Button type="submit" disabled={pending}>
                {pending ? <Spinner aria-hidden="true" data-icon="inline-start" /> : null}
                {pending ? t.upload.submitting : t.upload.submit}
              </Button>
            </div>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  )
}

function ReplaceSheet({
  document,
  replace,
  onClose,
  onDone,
}: {
  document: AdminDocument | null
  replace: DocumentsModel["replace"]
  onClose: () => void
  onDone: (text: string) => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [failure, setFailure] = useState<ActionFailure | null>(null)
  const [pending, setPending] = useState(false)

  function close() {
    setFile(null)
    setError(null)
    setFailure(null)
    onClose()
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!document) {
      return
    }
    const problem = fileProblem(file)
    if (problem || !file) {
      setError(problem ?? t.dropzone.required)
      return
    }
    setPending(true)
    const result = await replace(document.id, file)
    setPending(false)
    if (result.ok) {
      onDone(fill(t.replace.sent, { title: document.title }))
      close()
      return
    }
    setError(result.fieldErrors.file ?? null)
    setFailure(result.fieldErrors.file ? null : result)
  }

  return (
    <Sheet
      open={document !== null}
      onOpenChange={(open) => {
        if (!open && !pending) {
          close()
        }
      }}
    >
      <SheetContent side="right" className="w-full sm:max-w-md">
        <form noValidate className="flex h-full flex-col gap-4" onSubmit={(event) => void submit(event)}>
          <SheetHeader>
            <SheetTitle>{t.replace.title}</SheetTitle>
            <SheetDescription>
              {fill(t.replace.description, { title: document?.title ?? "" })}
            </SheetDescription>
          </SheetHeader>
          <div className="flex flex-col gap-3 px-4">
            <FileDropzone
              file={file}
              accept={acceptAttribute}
              error={error}
              disabled={pending}
              onFileChange={(next) => {
                setFile(next)
                setError(next ? fileProblem(next) : null)
              }}
            />
            {failure ? (
              <div className="flex flex-col gap-2">
                <p role="alert" className="text-body text-destructive">
                  {failure.message}
                </p>
                {failure.requestId ? <RequestIdCopy requestId={failure.requestId} /> : null}
              </div>
            ) : null}
          </div>
          <SheetFooter>
            <Button type="submit" disabled={pending}>
              {pending ? <Spinner aria-hidden="true" data-icon="inline-start" /> : null}
              {pending ? t.replace.submitting : t.replace.submit}
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  )
}
