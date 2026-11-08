/**
 * Tela de documentos do admin, em `/admin/documents`: o envio com
 * `FileDropzone`, a tabela do corpus e as ações de cada linha.
 *
 * Camada: view (SDD 13.2). Recebe o `DocumentsModel` de `useDocuments` pela
 * rota `app/routes/admin-documents.tsx` e não chama a API. Usa as regras de
 * `documents-model.ts`, o `DataTable`, o `FileDropzone` e o
 * `RequestIdCopy` de `components/patterns` e o `AlertDialog`, o `Sheet` e
 * o `Badge` de `components/ui`.
 *
 * SDD 15.5 (Documentos), 7.3 (ingestão), 12 e a Jornada J6 (15.3).
 */
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

// O aviso da região `aria-live`: o texto, o `request_id` de uma falha e se
// ele é uma falha.
type Notice = { text: string; requestId: string | null; failed: boolean }

const t = pt.documents

/**
 * Página de documentos: título, cartão de envio, região de avisos, tabela e
 * o `Sheet` de substituição.
 *
 * O resultado de cada ação é anunciado numa região `aria-live` (SDD 15.5).
 * Um sucesso entra com `role="status"`, e uma falha com `role="alert"` e o
 * `request_id` copiável.
 */
export function DocumentsScreen(model: DocumentsModel) {
  const [notice, setNotice] = useState<Notice | null>(null)
  // O documento do `Sheet` de substituição. `null` deixa o `Sheet` fechado.
  const [replacing, setReplacing] = useState<AdminDocument | null>(null)

  /** Anuncia um sucesso na região de avisos. */
  function announce(text: string) {
    setNotice({ text, requestId: null, failed: false })
  }

  /** Anuncia uma falha, com o `request_id` quando o servidor mandou um. */
  function report(result: ActionFailure) {
    setNotice({ text: result.message, requestId: result.requestId, failed: true })
  }

  // As colunas da seção 15.5: título, versão ativa, status, data e ações. O
  // título é o cabeçalho de cada linha para o leitor de tela.
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
          // Um erro de campo já aparece no próprio campo do cartão. Só as
          // outras falhas, como o 429, vão para a região de avisos.
          if (Object.keys(result.fieldErrors).length === 0) {
            report(result)
          }
        }}
      />

      {/* A região existe desde o início, vazia, para o leitor de tela
          anunciar cada aviso novo sem mover o foco. */}
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

/**
 * Célula do título: o título, o `slug` e, quando cabe, uma nota. Em
 * processamento com uma versão ativa, a nota avisa que a ativa continua
 * respondendo (FR-11). Na falha, mostra a versão e o erro da ingestão em
 * `--danger`, que `text-destructive` usa (SDD 15.5).
 */
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

/**
 * Ações de uma linha (SDD 15.5). Arquivado não tem ações, e uma falha ganha
 * Tentar de novo. Substituir fica desabilitado durante o processamento,
 * quando a API responderia 409. Arquivar pede confirmação num
 * `AlertDialog`.
 *
 * O nome acessível de cada botão começa pelo texto visível e termina com o
 * título do documento, para distinguir as linhas (SDD 15.8, WCAG 2.5.3).
 */
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
  // Os `useState` vêm antes do retorno antecipado abaixo: o React exige os
  // mesmos hooks, na mesma ordem, em toda renderização.
  const [pending, setPending] = useState<"retry" | "archive" | null>(null)
  const [confirming, setConfirming] = useState(false)
  const status = displayStatus(document)

  if (status === "archived") {
    return null
  }

  /**
   * Executa Tentar de novo ou Arquivar, fecha a confirmação e anuncia o
   * resultado com o título do documento.
   */
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
                // O Radix fecharia o diálogo no clique. O `preventDefault` o
                // mantém aberto, com o spinner, até a resposta; `run` o fecha.
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

/**
 * Cartão de envio (SDD 15.5): `FileDropzone`, título opcional e o botão
 * Enviar. O aviso de tipo e tamanho aparece antes do envio, pelo
 * `fileProblem`, sem chamar a API. No sucesso, o cartão volta vazio e a
 * tela anuncia o envio.
 */
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
  // Erros por campo, `file` e `title`, do navegador ou do servidor.
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [pending, setPending] = useState(false)

  /** Confere o arquivo, envia e mostra o resultado. */
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const problem = fileProblem(file)
    // O `!file` só estreita o tipo para o TypeScript: sem arquivo, o
    // `fileProblem` já devolve a mensagem.
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
              // Confere o arquivo assim que ele é escolhido ou solto. Texto
              // vazio quer dizer sem erro.
              onFileChange={(next) => {
                setFile(next)
                setErrors((current) => ({ ...current, file: next ? (fileProblem(next) ?? "") : "" }))
              }}
            />
            {/* O título vai até 200 caracteres, o limite da API (SDD 12).
                Sem título, a API usa o nome do arquivo. */}
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

/**
 * `Sheet` de substituição (SDD 15.5 e FR-11). Pede o arquivo da versão nova
 * e avisa que a versão ativa continua respondendo até a nova ficar pronta.
 * Fica aberto enquanto `document` não é nulo e não fecha durante o envio.
 */
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
  // O erro do arquivo, mostrado na área de upload.
  const [error, setError] = useState<string | null>(null)
  // Uma falha que não é do arquivo, como o 409, mostrada como alerta.
  const [failure, setFailure] = useState<ActionFailure | null>(null)
  const [pending, setPending] = useState(false)

  /** Limpa o estado e fecha, para a próxima abertura começar vazia. */
  function close() {
    setFile(null)
    setError(null)
    setFailure(null)
    onClose()
  }

  /** Confere o arquivo, envia a versão nova e fecha no sucesso. */
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
      // Esc, o botão fechar e o clique fora pedem para fechar. Durante o
      // envio, o pedido é ignorado.
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
