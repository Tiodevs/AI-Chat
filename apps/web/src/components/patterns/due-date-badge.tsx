import { CircleCheck, Clock, TriangleAlert } from "lucide-react"

import { Badge } from "@/components/ui/badge.tsx"
import { pt } from "@/i18n/pt.ts"

const dayMs = 24 * 60 * 60 * 1000

/** Prazo próximo: 3 dias ou menos. A cor só reforça o texto. SDD 14.2 e 15.5. */
export const dueSoonDays = 3

export type DueKind = "overdue" | "soon" | "ok" | "closed"

export type DueState = { kind: DueKind; days: number; text: string }

function fill(template: string, values: Record<string, string | number>) {
  return Object.entries(values).reduce(
    (text, [key, value]) => text.replaceAll(`{${key}}`, String(value)),
    template,
  )
}

export function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  })
}

/** Estado do prazo de um pedido de titular, contado em dias inteiros a partir de `now`. */
export function dueState({
  dueAt,
  closedAt,
  now,
}: {
  dueAt: string
  closedAt: string | null
  now: string
}): DueState {
  const t = pt.dueDate
  if (closedAt) {
    return { kind: "closed", days: 0, text: fill(t.closed, { date: formatDate(closedAt) }) }
  }
  const remaining = new Date(dueAt).getTime() - new Date(now).getTime()
  const days = Math.floor(Math.abs(remaining) / dayMs)
  if (remaining < 0) {
    const text = days === 0 ? t.overdueToday : days === 1 ? t.overdueOne : fill(t.overdueMany, { n: days })
    return { kind: "overdue", days, text }
  }
  const text = days === 0 ? t.dueToday : days === 1 ? t.dueOne : fill(t.dueMany, { n: days })
  return { kind: days <= dueSoonDays ? "soon" : "ok", days, text }
}

const variant = {
  overdue: "danger",
  soon: "warning",
  ok: "secondary",
  closed: "secondary",
} as const

const icon = {
  overdue: TriangleAlert,
  soon: Clock,
  ok: Clock,
  closed: CircleCheck,
}

/** Prazo de pedido de titular: badge com texto e a data do prazo. SDD 14.6 e 15.5 (FR-16). */
export function DueDateBadge({
  dueAt,
  closedAt = null,
  now,
}: {
  dueAt: string
  closedAt?: string | null
  now: string
}) {
  const state = dueState({ dueAt, closedAt, now })
  const Icon = icon[state.kind]
  return (
    <span className="flex flex-col items-start gap-1" data-due={state.kind}>
      <Badge variant={variant[state.kind]}>
        <Icon strokeWidth={1.75} aria-hidden="true" data-icon="inline-start" />
        {state.text}
      </Badge>
      <time dateTime={dueAt} className="text-caption text-muted-foreground">
        {fill(pt.dueDate.deadline, { date: formatDate(dueAt) })}
      </time>
    </span>
  )
}
