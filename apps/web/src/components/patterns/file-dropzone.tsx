import { CircleAlert, FileUp, X } from "lucide-react"
import { useId, useRef, useState, type DragEvent } from "react"

import { Button } from "@/components/ui/button.tsx"
import { pt } from "@/i18n/pt.ts"
import { cn } from "@/lib/utils.ts"

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
  onFileChange: (file: File | null) => void
  accept?: string
  error?: string | null
  disabled?: boolean
  label?: string
  hint?: string
  id?: string
}) {
  const generated = useId()
  const inputId = id ?? `${generated}-file`
  const hintId = `${inputId}-hint`
  const errorId = `${inputId}-error`
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const invalid = Boolean(error)

  function onDragOver(event: DragEvent<HTMLDivElement>) {
    if (disabled) {
      return
    }
    event.preventDefault()
    setDragging(true)
  }

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
