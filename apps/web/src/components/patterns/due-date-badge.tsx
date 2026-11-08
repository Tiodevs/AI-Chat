/**
 * Prazo de um pedido de titular, com o texto do estado e a data do prazo
 * (seções 14.6 e 15.5, FR-16).
 *
 * Aparece na fila de `/admin/privacy`, na coluna de prazo e no sheet do
 * pedido. Também exporta `dueState` e `formatDate`, que a tela e o teste
 * `features/admin/privacy-queue.test.tsx` usam.
 *
 * Estados: atrasado em `--danger` ("Atrasado há N dias"), prazo próximo
 * (3 dias ou menos) em `--warning`, no prazo e fechado no neutro
 * `secondary`. O texto e o ícone dizem o estado, nunca só a cor (seção
 * 15.8), e a data vai num `<time>` com `dateTime`. O `data-due` expõe o
 * estado para os testes.
 */
import { CircleCheck, Clock, TriangleAlert } from "lucide-react"

import { Badge } from "@/components/ui/badge.tsx"
import { pt } from "@/i18n/pt.ts"

// Um dia em milissegundos, para contar os dias inteiros até o prazo.
const dayMs = 24 * 60 * 60 * 1000

/** Prazo próximo: 3 dias ou menos. A cor só reforça o texto. SDD 14.2 e 15.5. */
export const dueSoonDays = 3

/** Estado do prazo: atrasado, próximo, em dia ou pedido fechado. */
export type DueKind = "overdue" | "soon" | "ok" | "closed"

/** O estado, os dias inteiros até o prazo (ou desde ele) e o texto. */
export type DueState = { kind: DueKind; days: number; text: string }

// Troca cada `{chave}` do texto de `pt` pelo valor.
function fill(template: string, values: Record<string, string | number>) {
  return Object.entries(values).reduce(
    (text, [key, value]) => text.replaceAll(`{${key}}`, String(value)),
    template,
  )
}

/** Data curta em pt-BR, como "15 de jan. de 2031". */
export function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  })
}

/**
 * Estado do prazo de um pedido de titular, contado em dias inteiros a
 * partir de `now`.
 *
 * 1. Pedido fechado: `closed`, com a data em que fechou.
 * 2. Conta os dias inteiros entre `now` e o prazo.
 * 3. Prazo vencido: `overdue`.
 * 4. Prazo correndo: `soon` com 3 dias ou menos, `ok` acima disso.
 */
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
  // 1. Um pedido fechado não tem prazo correndo.
  if (closedAt) {
    return { kind: "closed", days: 0, text: fill(t.closed, { date: formatDate(closedAt) }) }
  }
  // 2. Dias inteiros, arredondados para baixo: faltando 30 horas, conta
  // 1 dia. Na fila, `now` é o `generated_at` da resposta, relida a cada
  // 60 s (seção 15.5).
  const remaining = new Date(dueAt).getTime() - new Date(now).getTime()
  const days = Math.floor(Math.abs(remaining) / dayMs)
  // 3. Passou do prazo: atrasado, com "hoje", "1 dia" ou "N dias".
  if (remaining < 0) {
    const text = days === 0 ? t.overdueToday : days === 1 ? t.overdueOne : fill(t.overdueMany, { n: days })
    return { kind: "overdue", days, text }
  }
  // 4. Ainda no prazo: próximo com 3 dias ou menos, em dia acima disso.
  const text = days === 0 ? t.dueToday : days === 1 ? t.dueOne : fill(t.dueMany, { n: days })
  return { kind: days <= dueSoonDays ? "soon" : "ok", days, text }
}

// Variante do `Badge` por estado: os tons da seção 14.6.
const variant = {
  overdue: "danger",
  soon: "warning",
  ok: "secondary",
  closed: "secondary",
} as const

// Ícone por estado, que reforça o texto sem depender da cor.
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
  /** Prazo legal do pedido, em ISO 8601. */
  dueAt: string
  /** Quando o pedido foi concluído ou recusado; `null` se aberto. */
  closedAt?: string | null
  /** Agora, em ISO 8601. Vem de fora: a fila passa o `generated_at`. */
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
