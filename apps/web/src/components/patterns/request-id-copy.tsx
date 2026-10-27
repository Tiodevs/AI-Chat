import { useState } from "react"

import { Button } from "@/components/ui/button.tsx"
import { pt } from "@/i18n/pt.ts"

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
  busy?: boolean
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
