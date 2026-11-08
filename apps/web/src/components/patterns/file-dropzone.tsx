/**
 * Área de envio de arquivo, com arrastar e soltar e o botão de escolher
 * (seção 14.6).
 *
 * Aparece no envio de documento de `/admin/documents` e no sheet de
 * substituir documento, com o aviso de tipo e tamanho antes do envio
 * (seção 15.5). Só escolhe e mostra o arquivo: quem confere tipo e
 * tamanho e faz o envio é a tela, que devolve o problema em `error`.
 *
 * Estados: vazia, arrastando (borda `--ring`), com arquivo (nome,
 * tamanho e Remover), inválida (borda `--danger` e o erro com ícone) e
 * desabilitada durante o envio.
 *
 * Acessibilidade: o `<input type="file">` fica em `sr-only`, fora da
 * ordem de tabulação. Quem recebe o foco é o botão Escolher arquivo, que
 * leva a dica e o erro no `aria-describedby`; o rótulo também abre o
 * seletor. O erro tem `role="alert"`, e arrastar é só um atalho: tudo se
 * faz pelo botão.
 */
import { CircleAlert, FileUp, X } from "lucide-react"
import { useId, useRef, useState, type DragEvent } from "react"

import { Button } from "@/components/ui/button.tsx"
import { pt } from "@/i18n/pt.ts"
import { cn } from "@/lib/utils.ts"

/** Tamanho em KB (mínimo 1) abaixo de 1 MB, e em MB com uma casa acima. */
export function formatFileSize(bytes: number) {
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024)).toLocaleString("pt-BR")} KB`
  }
  return `${(bytes / (1024 * 1024)).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} MB`
}

/** Área de upload com arrastar e soltar e o botão de escolher. SDD 14.6. */
export function FileDropzone({
  file,
  onFileChange,
  accept,
  error,
  disabled = false,
  label = pt.documents.dropzone.label,
  hint = pt.documents.dropzone.hint,
  id,
}: {
  file: File | null
  /** Recebe o arquivo escolhido ou solto, ou `null` ao remover. */
  onFileChange: (file: File | null) => void
  /** Filtro do seletor do sistema, como `.md,.txt,.pdf`. */
  accept?: string
  error?: string | null
  disabled?: boolean
  label?: string
  hint?: string
  /** Id do campo; sem ele, o `useId` gera um. */
  id?: string
}) {
  const generated = useId()
  const inputId = id ?? `${generated}-file`
  const hintId = `${inputId}-hint`
  const errorId = `${inputId}-error`
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const invalid = Boolean(error)

  // Sem o `preventDefault` no `dragover`, o navegador não aceita o drop
  // e abre o arquivo na aba.
  function onDragOver(event: DragEvent<HTMLDivElement>) {
    if (disabled) {
      return
    }
    event.preventDefault()
    setDragging(true)
  }

  // Fica só com o primeiro arquivo solto: o envio é de um por vez.
  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setDragging(false)
    if (disabled) {
      return
    }
    const dropped = event.dataTransfer.files.item(0)
    if (dropped) {
      onFileChange(dropped)
    }
  }

  return (
    <div className="flex flex-col gap-2" data-slot="file-dropzone">
      <label htmlFor={inputId} className="text-label text-foreground">
        {label}
      </label>
      <div
        data-dragging={dragging ? "true" : undefined}
        data-invalid={invalid ? "true" : undefined}
        aria-disabled={disabled || undefined}
        onDragOver={onDragOver}
        onDragLeave={() => {
          setDragging(false)
        }}
        onDrop={onDrop}
        className={cn(
          "flex flex-col items-center gap-3 rounded-xl border border-dashed border-border bg-card px-4 py-6 text-center hover:bg-muted",
          dragging && "border-ring bg-muted",
          invalid && "border-danger",
          disabled && "pointer-events-none opacity-50",
        )}
      >
        <FileUp
          className="size-5 text-muted-foreground"
          strokeWidth={1.75}
          aria-hidden="true"
        />
        <p className="text-sm text-foreground">{pt.documents.dropzone.prompt}</p>
        <p id={hintId} className="text-caption text-muted-foreground">
          {hint}
        </p>
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          accept={accept}
          disabled={disabled}
          tabIndex={-1}
          className="sr-only"
          aria-invalid={invalid || undefined}
          aria-describedby={invalid ? `${hintId} ${errorId}` : hintId}
          // Limpar o valor deixa escolher o mesmo arquivo de novo: sem
          // isso, o navegador não dispara outro `change`.
          onChange={(event) => {
            onFileChange(event.target.files?.item(0) ?? null)
            event.target.value = ""
          }}
        />
        {file ? (
          <div className="flex max-w-full items-center gap-2">
            <span className="truncate text-sm text-foreground-strong">
              {pt.documents.dropzone.selected
                .replace("{name}", file.name)
                .replace("{size}", formatFileSize(file.size))}
            </span>
            {/* 32 px no desktop; no celular, o tamanho `icon` garante */}
            {/* 44 px de altura e de largura mínimas (seção 15.8). */}
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-8 shrink-0"
              aria-label={pt.documents.dropzone.clear}
              disabled={disabled}
              onClick={() => {
                onFileChange(null)
              }}
            >
              <X className="size-4" strokeWidth={1.75} />
            </Button>
          </div>
        ) : null}
        {/* O botão abre o seletor do sistema pelo `click()` do input. */}
        <Button
          type="button"
          variant="outline"
          disabled={disabled}
          aria-describedby={invalid ? `${hintId} ${errorId}` : hintId}
          aria-invalid={invalid || undefined}
          onClick={() => inputRef.current?.click()}
        >
          {pt.documents.dropzone.choose}
        </Button>
      </div>
      {invalid ? (
        <p
          id={errorId}
          role="alert"
          className="flex items-center gap-1.5 text-sm text-destructive"
        >
          <CircleAlert className="size-4 shrink-0" strokeWidth={1.75} aria-hidden="true" />
          {error}
        </p>
      ) : null}
    </div>
  )
}
