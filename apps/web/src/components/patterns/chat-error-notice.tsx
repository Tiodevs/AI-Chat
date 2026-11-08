/**
 * Aviso de falha dentro de uma conversa guiada, sem sair da tela.
 *
 * Usado no cadastro por conversa (`/register`), quando uma mensagem não é
 * enviada (seção 15.5): mostra a mensagem do erro, o `RequestIdCopy`,
 * Tentar de novo e Fechar, e o texto continua no compositor. Com o modelo
 * fora (503) ou sem sessão, a tela põe Usar o formulário em `children`.
 *
 * Acessibilidade: `role="alert"` anuncia a falha quando o aviso aparece.
 * O ícone é `aria-hidden`; o título e o texto dizem o problema, e a borda
 * `--danger` só reforça (seção 15.8). Fechar é um botão só de ícone, com
 * o nome "Fechar aviso", de 44 px no celular e 32 px no desktop.
 */
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
  /** Sem ele, não há Tentar de novo, como enquanto um envio está pendente. */
  onRetry?: () => void
  /** Sem ele, não há Fechar, como antes de existir uma sessão de cadastro. */
  onDismiss?: () => void
  /** Ações extras ao lado de Tentar de novo, como Usar o formulário. */
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
