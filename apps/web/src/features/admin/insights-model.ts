/**
 * Modelo da visão geral e da qualidade do admin: os tipos das respostas da
 * API, a ordem e a cor de cada desfecho, intenção e feedback, a variação
 * contra o período anterior e a formatação dos números. Só funções puras,
 * sem React e sem rede.
 *
 * Quem usa: `useInsights.ts`, `overview-screen.tsx` e `quality-screen.tsx`.
 * Usa o `pt` de `i18n/pt.ts`.
 *
 * SDD 12 (`/v1/admin/overview`, `/v1/admin/quality` e
 * `/v1/admin/conversations`), 11.8 (pseudonimização e revelação) e 15.5
 * (Visão geral e Qualidade).
 */
import { pt } from "@/i18n/pt.ts"

/** Os dois períodos que a API aceita em `period_days` (SDD 12). */
export const periods = [7, 30] as const
export type Period = (typeof periods)[number]

/**
 * Um indicador do período contra o período anterior de mesmo tamanho. A
 * API manda `null` quando falta denominador, como uma taxa sem respostas.
 */
export type Metric = { current: number | null; previous: number | null }

/**
 * Corpo de `GET /v1/admin/overview` (SDD 12). As taxas vêm de 0 a 1. A
 * tendência é por dia UTC, o funil conta as sessões de cadastro que
 * começaram no período e o orçamento é o do dia.
 */
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

/**
 * Uma conversa na lista da qualidade, pseudonimizada: `pseudonym` tem 8
 * caracteres do HMAC de `PSEUDONYM_KEY`, nunca nome nem e-mail (SDD 11.8 e
 * 12).
 */
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

/**
 * Corpo de `GET /v1/admin/quality`. As contagens são de todas as
 * conversas do período. A lista traz até 50 conversas, só de convidados e
 * de membros com `quality_improvement` vigente (SDD 11.8 e 12).
 */
export type Quality = {
  period_days: number
  outcomes: Record<string, number>
  feedback: Record<string, number>
  conversations: ConversationSummary[]
}

/**
 * Uma mensagem no inspetor, com o que a pessoa que opera precisa para
 * investigar: desfecho, versão do prompt, modelo, `request_id`, latência e
 * o rastro no LangSmith. `trace_url` é nulo sem
 * `LANGSMITH_RUN_URL_TEMPLATE`, e aí o inspetor mostra o `run_id` (SDD
 * 15.5 e 18.4).
 */
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

/**
 * Corpo de `GET /v1/admin/conversations/{id}`: a conversa pseudonimizada
 * com as mensagens. Cada leitura grava `conversation.view` (SDD 12).
 */
export type Inspection = {
  id: string
  subject_kind: "guest" | "member"
  pseudonym: string
  created_at: string
  messages: InspectorMessage[]
}

/**
 * Os tons de status. Cada tela traduz o tom para a variante do `Badge` ou
 * para a cor do segmento. Verde, vermelho, âmbar e azul só aparecem como
 * status (SDD 14.1 e 14.2).
 */
export type Tone = "success" | "warning" | "danger" | "info" | "neutral"

/** Os desfechos de uma resposta, na ordem dos segmentos e do filtro. */
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

/** Um dos desfechos de `outcomeOrder`. */
export type OutcomeKey = (typeof outcomeOrder)[number]

/**
 * Tom de cada desfecho. As duas formas de abstenção ficam em `warning`, e
 * a recusa médica e o erro em `danger`.
 */
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

/** As três situações de feedback, na ordem dos segmentos e do filtro. */
export const feedbackOrder = ["helpful", "not_helpful", "none"] as const
export const feedbackTone: Record<(typeof feedbackOrder)[number], Tone> = {
  helpful: "success",
  not_helpful: "danger",
  none: "neutral",
}

/**
 * As intenções, derivadas pela API do desfecho gravado: `refused` conta
 * como orientação médica, `off_topic` como fora do tema e o resto como
 * informação pública (SDD 15.5).
 */
export const intentOrder = ["public_info", "medical_advice", "off_topic"] as const
export const intentTone: Record<(typeof intentOrder)[number], Tone> = {
  public_info: "info",
  medical_advice: "danger",
  off_topic: "neutral",
}

/**
 * Nome de um desfecho em português. Um desfecho desconhecido aparece cru,
 * e a falta de desfecho vira "Sem dados".
 */
export function outcomeLabel(outcome: string | null) {
  if (!outcome) {
    return pt.insights.notAvailable
  }
  return (pt.insights.outcomes as Record<string, string>)[outcome] ?? outcome
}

/** Guarda de tipo para `OutcomeKey`. Nenhuma tela a usa hoje. */
export function isOutcome(value: string): value is OutcomeKey {
  return (outcomeOrder as readonly string[]).includes(value)
}

// Formatadores de número em português. As taxas mostram até uma casa
// decimal, como "42,5%".
const integer = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 })
const percentFormat = new Intl.NumberFormat("pt-BR", {
  style: "percent",
  maximumFractionDigits: 1,
})

/** Contagem em português, com separador de milhar. */
export function formatCount(value: number) {
  return integer.format(value)
}

/** Taxa de 0 a 1 em porcentagem, com até uma casa decimal. */
export function formatPercent(value: number) {
  return percentFormat.format(value)
}

/** Sentido da variação. `none` é a falta de período anterior para comparar. */
export type DeltaDirection = "up" | "down" | "flat" | "none"

/**
 * Variação relativa para contagens e em pontos percentuais para taxas.
 *
 * Uma contagem compara em porcentagem: de 10 para 12 perguntas é "Alta de
 * 20%". Uma taxa compara pela diferença: de 40% para 45% é "Alta de 5
 * p.p.". Sem um dos valores, ou com contagem anterior zero, não há base, e
 * o texto diz "Sem período anterior".
 */
export function delta(metric: Metric, kind: "count" | "rate") {
  const { current, previous } = metric
  if (current == null || previous == null || (kind === "count" && previous === 0)) {
    return { direction: "none" as DeltaDirection, text: pt.insights.delta.none }
  }
  const change = kind === "count" ? (current - previous) / previous : current - previous
  // 0,0005 é metade da última casa exibida (0,1% ou 0,1 p.p.). Abaixo disso
  // o número formatado daria zero, então vale "Sem variação".
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

/** Um segmento do `SegmentedStatusCard`: chave, nome, contagem e tom. */
export type Segment = { key: string; label: string; count: number; tone: Tone }

/**
 * Monta os segmentos na ordem dada. Uma chave sem contagem na resposta
 * entra com zero, para a barra e a legenda terem sempre os mesmos itens.
 */
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

/**
 * Rótulo curto de um dia da tendência, como "03 de nov.". A API agrupa por
 * dia UTC e manda só a data; ler a data e formatar em UTC evita que um fuso
 * negativo, como o de Brasília, mostre o dia anterior.
 */
export function formatDay(iso: string) {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "short",
    timeZone: "UTC",
  })
}

/** Nome de quem conversou sem identidade, como "Convidado a1b2c3d4". */
export function subjectLabel(kind: "guest" | "member", pseudonym: string) {
  return pt.quality.subject.label
    .replace("{kind}", pt.quality.subject[kind])
    .replace("{pseudonym}", pseudonym)
}

/**
 * Mesma regra do servidor para o motivo da revelação: de 10 a 500
 * caracteres depois de juntar os espaços (SDD 12). Conferir aqui evita um
 * pedido que voltaria 422.
 */
export function reasonIsValid(reason: string) {
  const clean = reason.trim().split(/\s+/).join(" ")
  return clean.length >= 10 && clean.length <= 500
}
