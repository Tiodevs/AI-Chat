/**
 * O `request_id` de um erro, em fonte mono, com o botão de copiar
 * (seção 14.6).
 *
 * Aparece em toda tela de erro: o error boundary de cada rota (seção
 * 13.3), o erro da conversa, o `ChatErrorNotice` e as falhas da conta, do
 * canal do titular, do cadastro por formulário e do admin. Com o id, quem
 * opera acha o log e o rastro do pedido (seção 18).
 *
 * Usa a API de área de transferência do navegador; se ela falhar, o botão
 * continua "Copiar". O botão usa `aria-pressed` para dizer que já copiou.
 * As props `disabled`, `autoFocus`, `busy` e `initialCopied` só aparecem
 * nas histórias do Storybook.
 */
import { useState } from "react"

import { Button } from "@/components/ui/button.tsx"
import { pt } from "@/i18n/pt.ts"

/** Rótulo, id e botão de copiar, empilhados. */
export function RequestIdCopy({
  requestId,
  disabled = false,
  autoFocus = false,
  busy = false,
  initialCopied = false,
}: {
  requestId: string
  disabled?: boolean
  autoFocus?: boolean
  /** Desabilita o botão e marca `aria-busy`. */
  busy?: boolean
  /** Começa no estado "Copiado", para a história mostrar esse estado. */
  initialCopied?: boolean
}) {
  const [copied, setCopied] = useState(initialCopied)

  async function copy() {
    try {
      await navigator.clipboard.writeText(requestId)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className="flex flex-col items-start gap-2">
      <p className="text-body text-muted-foreground">{pt.requestId.label}</p>
      <p className="font-mono text-body text-foreground">{requestId}</p>
      <Button
        type="button"
        variant="outline"
        onClick={() => {
          void copy()
        }}
        disabled={disabled || busy}
        autoFocus={autoFocus}
        aria-pressed={copied}
        aria-busy={busy || undefined}
      >
        {copied ? pt.requestId.copied : pt.requestId.copy}
      </Button>
    </div>
  )
}
