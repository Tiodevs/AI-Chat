import { pt } from "@/i18n/pt.ts"
import { cn } from "@/lib/utils.ts"

const kinds = {
  answered: "success",
  abstained: "warning",
  refused: "danger",
  replaced: "warning",
  unavailable: "info",
} as const

export type OutcomeKind = keyof typeof kinds

const surfaces = {
  success: "bg-[color-mix(in_oklab,var(--success)_15%,transparent)]",
  warning: "bg-[color-mix(in_oklab,var(--warning)_15%,transparent)]",
  danger: "bg-[color-mix(in_oklab,var(--danger)_15%,transparent)]",
  info: "bg-[color-mix(in_oklab,var(--info)_15%,transparent)]",
} as const

const dots = {
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  info: "bg-info",
} as const

export function OutcomeBadge({ kind }: { kind: OutcomeKind }) {
  const tone = kinds[kind]
  return (
    <span
      className={cn(
        "inline-flex w-fit items-center gap-2 rounded-full px-2.5 py-1 text-caption text-foreground",
        surfaces[tone]
      )}
    >
      <span
        aria-hidden="true"
        className={cn("size-2 rounded-full", dots[tone])}
      />
      {pt.ask.outcomes[kind]}
    </span>
  )
}
