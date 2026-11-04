import { CircleAlert, X } from "lucide-react"
import type { ReactNode } from "react"

import { RequestIdCopy } from "@/components/patterns/request-id-copy.tsx"
import { Button } from "@/components/ui/button.tsx"
import { pt } from "@/i18n/pt.ts"

/** Aviso de falha dentro de uma conversa. O visitante fica na tela e escolhe o próximo passo. */
export function ChatErrorNotice({
  title,
  message,
  requestId,
  onRetry,
  onDismiss,
  children,
}: {
  title: string
  message: string
  requestId: string | null
  onRetry?: () => void
  onDismiss?: () => void
  children?: ReactNode
}) {
  return (
    <div
      role="alert"
      className="flex gap-3 rounded-2xl border border-danger bg-card px-4 py-3"
    >
      <CircleAlert
        className="mt-0.5 size-4 shrink-0 text-danger"
        strokeWidth={1.75}
        aria-hidden="true"
      />
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <p className="text-label text-foreground-strong">{title}</p>
        <p className="text-body text-foreground">{message}</p>
        {requestId ? <RequestIdCopy requestId={requestId} /> : null}
        {onRetry || children ? (
          <div className="flex flex-wrap items-center gap-2">
            {onRetry ? (
              <Button
                type="button"
                variant="outline"
                className="min-h-11 md:min-h-8"
                onClick={onRetry}
              >
                {pt.registration.retry}
              </Button>
            ) : null}
            {children}
          </div>
        ) : null}
      </div>
      {onDismiss ? (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-11 shrink-0 md:size-8"
          aria-label={pt.registration.dismiss}
          onClick={onDismiss}
        >
          <X className="size-4" strokeWidth={1.75} />
        </Button>
      ) : null}
    </div>
  )
}
