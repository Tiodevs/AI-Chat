import { cn } from "@/lib/utils.ts"

import { toneDot, type Tone } from "./tone.ts"

/** Bloco de contagem, como Ready e Processing na imagem. SDD 14.6. */
export function StatTile({
  label,
  value,
  detail,
  tone = "neutral",
}: {
  label: string
  value: string
  detail?: string
  tone?: Tone
}) {
  return (
    <div className="flex min-w-0 flex-col gap-1 rounded-lg bg-muted px-3 py-2.5">
      <span className="flex items-center gap-2 text-caption text-muted-foreground">
        <span aria-hidden="true" className={cn("size-2 shrink-0 rounded-full", toneDot[tone])} />
        <span className="truncate">{label}</span>
      </span>
      <span className="text-body font-medium text-foreground-strong tabular-nums">
        {value}
        {detail ? (
          <span className="ml-1.5 text-caption font-normal text-subtle-foreground">{detail}</span>
        ) : null}
      </span>
    </div>
  )
}
