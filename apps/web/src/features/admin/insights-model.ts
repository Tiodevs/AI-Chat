import { pt } from "@/i18n/pt.ts"

export const periods = [7, 30] as const
export type Period = (typeof periods)[number]

export type Metric = { current: number | null; previous: number | null }

export type Overview = {
  period_days: number
  generated_at: string
  questions: Metric
  answer_rate: Metric
  abstention_rate: Metric
  helpful_rate: Metric
  trend: { date: string; questions: number; answered: number }[]
  outcomes: Record<string, number>
  intents: Record<string, number>
  feedback: Record<string, number>
  funnel: { step: "started" | "password_set" | "completed"; chat: number; form: number }[]
  budget: { used_tokens: number; daily_budget: number; ratio: number }
}

export type ConversationSummary = {
  id: string
  subject_kind: "guest" | "member"
  pseudonym: string
  started_at: string
  last_activity_at: string
  questions: number
  last_outcome: string | null
  helpful: number
  not_helpful: number
}

export type Quality = {
  period_days: number
  outcomes: Record<string, number>
  feedback: Record<string, number>
  conversations: ConversationSummary[]
}

export type InspectorMessage = {
  id: string
  role: "user" | "assistant"
  content: string
  created_at: string
  outcome: string | null
  prompt_version: string | null
  model: string | null
  request_id: string | null
  latency_ms: number | null
  run_id: string | null
  trace_url: string | null
  citations: { index: number; document_title: string; heading: string | null }[]
  rating: number | null
}

export type Inspection = {
  id: string
  subject_kind: "guest" | "member"
  pseudonym: string
  created_at: string
  messages: InspectorMessage[]
}

export type Tone = "success" | "warning" | "danger" | "info" | "neutral"

export const outcomeOrder = [
  "answered",
  "abstained",
  "grounding_failed",
  "refused",
  "off_topic",
  "cancelled",
  "degraded",
  "error",
] as const

export type OutcomeKey = (typeof outcomeOrder)[number]

export const outcomeTone: Record<OutcomeKey, Tone> = {
  answered: "success",
  abstained: "warning",
  grounding_failed: "warning",
  refused: "danger",
  off_topic: "neutral",
  cancelled: "neutral",
  degraded: "info",
  error: "danger",
}

export const feedbackOrder = ["helpful", "not_helpful", "none"] as const
export const feedbackTone: Record<(typeof feedbackOrder)[number], Tone> = {
  helpful: "success",
  not_helpful: "danger",
  none: "neutral",
}

export const intentOrder = ["public_info", "medical_advice", "off_topic"] as const
export const intentTone: Record<(typeof intentOrder)[number], Tone> = {
  public_info: "info",
  medical_advice: "danger",
  off_topic: "neutral",
}

export function outcomeLabel(outcome: string | null) {
  if (!outcome) {
    return pt.insights.notAvailable
  }
  return (pt.insights.outcomes as Record<string, string>)[outcome] ?? outcome
}

export function isOutcome(value: string): value is OutcomeKey {
  return (outcomeOrder as readonly string[]).includes(value)
}

const integer = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 })
const percentFormat = new Intl.NumberFormat("pt-BR", {
  style: "percent",
  maximumFractionDigits: 1,
})

export function formatCount(value: number) {
  return integer.format(value)
}

export function formatPercent(value: number) {
  return percentFormat.format(value)
}

export type DeltaDirection = "up" | "down" | "flat" | "none"

/** Variação relativa para contagens e em pontos percentuais para taxas. */
export function delta(metric: Metric, kind: "count" | "rate") {
  const { current, previous } = metric
  if (current == null || previous == null || (kind === "count" && previous === 0)) {
    return { direction: "none" as DeltaDirection, text: pt.insights.delta.none }
  }
  const change = kind === "count" ? (current - previous) / previous : current - previous
  if (Math.abs(change) < 0.0005) {
    return { direction: "flat" as DeltaDirection, text: pt.insights.delta.flat }
  }
  const magnitude =
    kind === "count"
      ? formatPercent(Math.abs(change))
      : `${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(Math.abs(change) * 100)} p.p.`
  const direction: DeltaDirection = change > 0 ? "up" : "down"
  return {
    direction,
    text: (direction === "up" ? pt.insights.delta.up : pt.insights.delta.down).replace(
      "{value}",
      magnitude,
    ),
  }
}

export type Segment = { key: string; label: string; count: number; tone: Tone }

export function segmentsFrom<K extends string>(
  order: readonly K[],
  counts: Record<string, number>,
  labels: Record<K, string>,
  tones: Record<K, Tone>,
): Segment[] {
  return order.map((key) => ({
    key,
    label: labels[key],
    count: counts[key] ?? 0,
    tone: tones[key],
  }))
}

export function formatDay(iso: string) {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "short",
    timeZone: "UTC",
  })
}

export function subjectLabel(kind: "guest" | "member", pseudonym: string) {
  return pt.quality.subject.label
    .replace("{kind}", pt.quality.subject[kind])
    .replace("{pseudonym}", pseudonym)
}

export function reasonIsValid(reason: string) {
  const clean = reason.trim().split(/\s+/).join(" ")
  return clean.length >= 10 && clean.length <= 500
}
