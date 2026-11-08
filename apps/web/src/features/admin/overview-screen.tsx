/**
 * Visão geral do admin, em `/admin`: quatro indicadores, a tendência de
 * perguntas, os desfechos, o funil de cadastro e o orçamento do dia.
 *
 * Camada: view (SDD 13.2). Recebe o `OverviewModel` de `useOverview` pela
 * rota `app/routes/admin.tsx` e não chama a API. Usa os cartões de
 * `components/patterns` (`StatCard`, `TrendChartCard`, `SegmentedStatusCard`
 * e `GroupedBarCard`, os dois gráficos em Recharts) e as regras de
 * `insights-model.ts`.
 *
 * SDD 15.5 (Visão geral do admin), 14.6 (componentes), 15.8 (tabela
 * equivalente a cada gráfico) e 16.3 (movimentos M2, M3, M4 e M15).
 */
import { PageHeading } from "@/app/page-heading.tsx"
import { GroupedBarCard } from "@/components/patterns/grouped-bar-card.tsx"
import { SegmentedStatusCard } from "@/components/patterns/segmented-status-card.tsx"
import { StatCard } from "@/components/patterns/stat-card.tsx"
import { TrendChartCard } from "@/components/patterns/trend-chart-card.tsx"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card.tsx"
import { Progress } from "@/components/ui/progress.tsx"
import { Skeleton } from "@/components/ui/skeleton.tsx"
import { pt } from "@/i18n/pt.ts"
import { cn } from "@/lib/utils.ts"

import {
  delta,
  feedbackOrder,
  feedbackTone,
  formatCount,
  formatDay,
  formatPercent,
  intentOrder,
  intentTone,
  outcomeOrder,
  outcomeTone,
  periods,
  segmentsFrom,
  type Metric,
  type Overview,
  type Period,
} from "./insights-model.ts"
import type { OverviewModel } from "./useInsights.ts"

const t = pt.insights

/**
 * Como mostrar um indicador: a chave na resposta, o nome, se é contagem ou
 * taxa e o sentido em que a variação é boa.
 */
type StatSpec = {
  key: "questions" | "answer_rate" | "abstention_rate" | "helpful_rate"
  label: string
  kind: "count" | "rate"
  goodWhen: "up" | "down"
}

// Os quatro indicadores da seção 15.5. Na abstenção, cair é bom: o
// `DeltaBadge` mostra a queda em `--success` e a alta em `--danger`.
const stats: StatSpec[] = [
  { key: "questions", label: t.stats.questions, kind: "count", goodWhen: "up" },
  { key: "answer_rate", label: t.stats.answerRate, kind: "rate", goodWhen: "up" },
  { key: "abstention_rate", label: t.stats.abstentionRate, kind: "rate", goodWhen: "down" },
  { key: "helpful_rate", label: t.stats.helpfulRate, kind: "rate", goodWhen: "up" },
]

/** O formatador do valor: contagem inteira ou porcentagem. */
function formatter(kind: "count" | "rate") {
  return kind === "count" ? formatCount : formatPercent
}

/**
 * Nome acessível do cartão, com o valor final e a variação, como
 * "Perguntas: 120. Alta de 20%". O número visível sobe animado (M2), mas o
 * leitor de tela lê o valor final desde o início (SDD 16.3).
 */
function statLabel(spec: StatSpec, metric: Metric | undefined) {
  const change = metric ? delta(metric, spec.kind) : { text: t.delta.none }
  const value =
    metric?.current == null ? t.notAvailable : formatter(spec.kind)(metric.current)
  return t.stats.ariaLabel
    .replace("{label}", spec.label)
    .replace("{value}", value)
    .replace("{delta}", change.text)
}

/**
 * Página da visão geral. Os quatro cartões aparecem desde o início, com
 * skeleton dentro enquanto carregam. Os gráficos esperam os dados, com
 * skeletons do mesmo tamanho no lugar.
 */
export function OverviewScreen(model: OverviewModel) {
  const data = model.overview
  // A legenda de cada cartão, como "contra os 7 dias anteriores".
  const caption = t.period.comparedTo.replace("{days}", String(model.period))
  return (
    <div className="flex flex-col gap-6">
      <PageHeading title={pt.pages.admin} />
      {model.loadError ? (
        <p role="alert" className="text-body text-destructive">
          {t.loadFailed}
        </p>
      ) : null}
      {/* A região dos cartões leva o nome "Perguntas", o mesmo do primeiro
          cartão, e não um nome para o grupo dos quatro. */}
      <section aria-label={t.stats.questions} className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((spec) => {
          const metric = data?.[spec.key]
          return (
            <StatCard
              key={spec.key}
              label={spec.label}
              value={metric?.current ?? null}
              format={formatter(spec.kind)}
              // Na animação, a taxa anda em passos de 0,001: a menor
              // diferença que a porcentagem com uma casa decimal mostra.
              decimals={spec.kind === "rate" ? 3 : 0}
              delta={metric ? delta(metric, spec.kind) : { direction: "none", text: t.delta.none }}
              goodWhen={spec.goodWhen}
              caption={caption}
              emptyText={t.notAvailable}
              ariaLabel={statLabel(spec, metric)}
              loading={model.loading}
            />
          )
        })}
      </section>
      {data ? (
        <OverviewCharts data={data} period={model.period} onPeriodChange={model.setPeriod} />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2" aria-busy="true" aria-label={pt.loading}>
          <Skeleton className="h-72 w-full lg:col-span-2" />
          <Skeleton className="h-56 w-full" />
          <Skeleton className="h-56 w-full" />
        </div>
      )}
    </div>
  )
}

/**
 * Os gráficos da visão geral. O seletor de período fica no cartão da
 * tendência, mas muda o `period` da tela toda, cartões incluídos (SDD
 * 15.5). Os dois gráficos do Recharts ficam escondidos do leitor de tela,
 * que lê a tabela equivalente montada pelo próprio cartão (SDD 15.8).
 */
function OverviewCharts({
  data,
  period,
  onPeriodChange,
}: {
  data: Overview
  period: Period
  onPeriodChange: (period: Period) => void
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="lg:col-span-2">
        <TrendChartCard
          title={t.trend.title}
          // Um ponto por dia UTC do período: o total de perguntas e as
          // respondidas.
          points={data.trend.map((point) => ({
            key: point.date,
            label: formatDay(point.date),
            primary: point.questions,
            secondary: point.answered,
          }))}
          primaryLabel={t.trend.questions}
          secondaryLabel={t.trend.answered}
          dateLabel={t.trend.date}
          tableCaption={t.trend.tableCaption}
          periodLabel={t.period.label}
          periods={periods.map((value) => ({
            value: String(value),
            label: value === 7 ? t.period.days7 : t.period.days30,
          }))}
          period={String(period)}
          // O valor chega como texto. Qualquer coisa que não seja 30 vale 7,
          // então a API nunca recebe um período fora de 7 e 30.
          onPeriodChange={(value) => {
            onPeriodChange(Number(value) === 30 ? 30 : 7)
          }}
        />
      </div>
      {/* Desfechos com as abas Desfecho, Intenção e Feedback (SDD 15.5). */}
      <SegmentedStatusCard
        title={t.outcomesCard.title}
        emptyText={t.outcomesCard.empty}
        views={[
          {
            key: "outcome",
            label: t.outcomesCard.outcome,
            segments: segmentsFrom(outcomeOrder, data.outcomes, t.outcomes, outcomeTone),
          },
          {
            key: "intent",
            label: t.outcomesCard.intent,
            segments: segmentsFrom(intentOrder, data.intents, t.intents, intentTone),
          },
          {
            key: "feedback",
            label: t.outcomesCard.feedback,
            segments: segmentsFrom(feedbackOrder, data.feedback, t.feedback, feedbackTone),
          },
        ]}
      />
      {/* Funil de cadastro: conversa contra formulário em cada etapa. */}
      <GroupedBarCard
        title={t.funnel.title}
        rows={data.funnel.map((row) => ({
          key: row.step,
          label: t.funnel.steps[row.step],
          first: row.chat,
          second: row.form,
        }))}
        firstLabel={t.funnel.chat}
        secondLabel={t.funnel.form}
        categoryLabel={t.funnel.step}
        tableCaption={t.funnel.tableCaption}
      />
      <BudgetCard budget={data.budget} />
    </div>
  )
}

/**
 * Orçamento diário de tokens (SDD 15.5 e 7.1): o uso do dia em porcentagem
 * e em tokens, com uma barra `Progress`. Perto do limite, a barra fica em
 * `--warning` e o aviso diz que as respostas param em 100%. Com
 * `daily_budget` zero, o teto está desligado e o cartão mostra só os tokens
 * usados.
 */
function BudgetCard({ budget }: { budget: Overview["budget"] }) {
  // A barra vai até 100: depois do teto, `ratio` passa de 1, e o texto ao
  // lado mostra o valor real.
  const percent = Math.min(100, Math.round(budget.ratio * 100))
  // A seção 15.5 diz "acima de 80%". O código já pinta em 80% exatos.
  const near = budget.ratio >= 0.8
  const used = formatCount(budget.used_tokens)
  return (
    <Card className="gap-4">
      <CardHeader>
        <CardTitle>
          <h2 className="text-label text-foreground-strong">{t.budget.title}</h2>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {budget.daily_budget > 0 ? (
          <>
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-metric text-foreground-strong tabular-nums">
                {formatPercent(budget.ratio)}
              </span>
              <span className="text-caption text-subtle-foreground">
                {t.budget.used
                  .replace("{used}", used)
                  .replace("{budget}", formatCount(budget.daily_budget))}
              </span>
            </div>
            {/* O seletor arbitrário do Tailwind pinta o indicador interno do
                `Progress`, o filho com `data-slot="progress-indicator"`. */}
            <Progress
              value={percent}
              aria-label={t.budget.label}
              className={cn(near && "[&>[data-slot=progress-indicator]]:bg-warning")}
            />
            {near ? <p className="text-caption text-foreground">{t.budget.nearLimit}</p> : null}
          </>
        ) : (
          <p className="text-body text-muted-foreground">{t.budget.unlimited.replace("{used}", used)}</p>
        )}
      </CardContent>
    </Card>
  )
}
