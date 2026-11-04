import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card.tsx"
import { ChartContainer, type ChartConfig } from "@/components/ui/chart.tsx"

export type GroupedBarRow = { key: string; label: string; first: number; second: number }

/**
 * Barras agrupadas, como Retention Rate na imagem: duas séries por etapa. O gráfico
 * fica escondido de leitores de tela, que leem a tabela equivalente. SDD 14.6 e 15.8.
 */
export function GroupedBarCard({
  title,
  rows,
  firstLabel,
  secondLabel,
  categoryLabel,
  tableCaption,
}: {
  title: string
  rows: GroupedBarRow[]
  firstLabel: string
  secondLabel: string
  categoryLabel: string
  tableCaption: string
}) {
  const config = {
    first: { label: firstLabel, color: "var(--chart-1)" },
    second: { label: secondLabel, color: "var(--chart-3)" },
  } satisfies ChartConfig

  return (
    <Card className="gap-4">
      <CardHeader>
        <CardTitle>
          <h2 className="text-label text-foreground-strong">{title}</h2>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-4 pb-3 text-caption text-muted-foreground" aria-hidden="true">
          <span className="flex items-center gap-2">
            <span className="size-2 rounded-sm bg-chart-1" />
            {firstLabel}
          </span>
          <span className="flex items-center gap-2">
            <span className="size-2 rounded-sm bg-chart-3" />
            {secondLabel}
          </span>
        </div>
        <div aria-hidden="true">
          <ChartContainer config={config} className="aspect-auto h-56 w-full">
            <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -16 }} barGap={4}>
              <CartesianGrid vertical={false} stroke="var(--border)" />
              <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} />
              <YAxis allowDecimals={false} tickLine={false} axisLine={false} width={40} />
              <Bar dataKey="first" fill="var(--color-first)" radius={4} isAnimationActive={false} />
              <Bar dataKey="second" fill="var(--color-second)" radius={4} isAnimationActive={false} />
            </BarChart>
          </ChartContainer>
        </div>
        <table className="sr-only">
          <caption>{tableCaption}</caption>
          <thead>
            <tr>
              <th scope="col">{categoryLabel}</th>
              <th scope="col">{firstLabel}</th>
              <th scope="col">{secondLabel}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key}>
                <th scope="row">{row.label}</th>
                <td>{row.first}</td>
                <td>{row.second}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}
