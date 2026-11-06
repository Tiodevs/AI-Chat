import { useRef, useState } from "react"
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card.tsx"
import { ChartContainer, type ChartConfig } from "@/components/ui/chart.tsx"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group.tsx"
import { useGSAP } from "@/motion/gsap.ts"
import { useMotion } from "@/motion/MotionProvider.tsx"
import { presets } from "@/motion/presets.ts"

export type TrendPoint = { key: string; label: string; primary: number; secondary: number }

/**
 * Série no tempo com cursor e pílula de data invertida, como Revenue over time.
 * M3 revela o gráfico com scaleX e M4 move cursor e tooltip com quickTo. A tabela
 * equivalente fica para leitores de tela. SDD 14.6, 15.8 e 16.3.
 */
export function TrendChartCard({
  title,
  points,
  primaryLabel,
  secondaryLabel,
  dateLabel,
  tableCaption,
  periodLabel,
  periods,
  period,
  onPeriodChange,
}: {
  title: string
  points: TrendPoint[]
  primaryLabel: string
  secondaryLabel: string
  dateLabel: string
  tableCaption: string
  periodLabel: string
  periods: { value: string; label: string }[]
  period: string
  onPeriodChange: (value: string) => void
}) {
  const rootRef = useRef<HTMLDivElement>(null)
  const plotRef = useRef<HTMLDivElement>(null)
  const pointerRef = useRef<HTMLDivElement>(null)
  const moveRef = useRef<((x: number, y: number) => void) | null>(null)
  const [hovered, setHovered] = useState<number | null>(null)
  const { reduced } = useMotion()
  const signature = points.map((point) => `${point.key}:${String(point.primary)}`).join("|")

  useGSAP(
    () => {
      presets.revealChart(plotRef.current, reduced)
      moveRef.current = presets.followPointer(pointerRef.current, reduced)
    },
    { dependencies: [signature, reduced], scope: rootRef },
  )

  const config = {
    primary: { label: primaryLabel, color: "var(--chart-1)" },
    secondary: { label: secondaryLabel, color: "var(--chart-2)" },
  } satisfies ChartConfig
  const active = hovered == null ? null : points[hovered]

  return (
    <Card ref={rootRef} className="gap-4">
      <CardHeader className="flex flex-wrap items-center justify-between gap-3">
        <CardTitle>
          <h2 className="text-label text-foreground-strong">{title}</h2>
        </CardTitle>
        <ToggleGroup
          type="single"
          value={period}
          aria-label={periodLabel}
          onValueChange={(value) => {
            if (value) {
              onPeriodChange(value)
            }
          }}
        >
          {periods.map((option) => (
            <ToggleGroupItem key={option.value} value={option.value}>
              {option.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-4 pb-3 text-caption text-muted-foreground" aria-hidden="true">
          <span className="flex items-center gap-2">
            <span className="h-0.5 w-4 rounded-full bg-chart-1" />
            {primaryLabel}
          </span>
          <span className="flex items-center gap-2">
            <span className="h-0.5 w-4 rounded-full bg-chart-2" />
            {secondaryLabel}
          </span>
        </div>
        <div className="relative" aria-hidden="true" onMouseLeave={() => { setHovered(null) }}>
          <div ref={plotRef}>
            <ChartContainer config={config} className="aspect-auto h-56 w-full">
              <AreaChart
                accessibilityLayer={false}
                data={points}
                margin={{ top: 8, right: 8, bottom: 0, left: -16 }}
                onMouseMove={(state) => {
                  const index = state.activeTooltipIndex == null ? null : Number(state.activeTooltipIndex)
                  const x = state.activeCoordinate?.x
                  if (index == null || Number.isNaN(index) || x == null) {
                    return
                  }
                  setHovered(index)
                  moveRef.current?.(x, 0)
                }}
              >
                <defs>
                  <linearGradient id="trend-fill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--color-primary)" stopOpacity={0.16} />
                    <stop offset="100%" stopColor="var(--color-primary)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid vertical={false} stroke="var(--border)" />
                <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} minTickGap={24} />
                <YAxis allowDecimals={false} tickLine={false} axisLine={false} width={40} />
                <Area
                  dataKey="primary"
                  type="monotone"
                  stroke="var(--color-primary)"
                  strokeWidth={1.5}
                  fill="url(#trend-fill)"
                  isAnimationActive={false}
                  activeDot={false}
                />
                <Area
                  dataKey="secondary"
                  type="monotone"
                  stroke="var(--color-secondary)"
                  strokeWidth={1.5}
                  strokeDasharray="4 4"
                  fill="none"
                  isAnimationActive={false}
                  activeDot={false}
                />
              </AreaChart>
            </ChartContainer>
          </div>
          <div
            ref={pointerRef}
            className="pointer-events-none absolute inset-y-0 left-0 flex flex-col items-center"
            style={{ visibility: active ? "visible" : "hidden" }}
          >
            <span className="-translate-x-1/2 rounded-md bg-primary px-2 py-0.5 text-caption whitespace-nowrap text-primary-foreground">
              {active ? `${active.label} · ${String(active.primary)} / ${String(active.secondary)}` : ""}
            </span>
            <span className="w-px flex-1 -translate-x-1/2 bg-ring" />
          </div>
        </div>
        <table className="sr-only">
          <caption>{tableCaption}</caption>
          <thead>
            <tr>
              <th scope="col">{dateLabel}</th>
              <th scope="col">{primaryLabel}</th>
              <th scope="col">{secondaryLabel}</th>
            </tr>
          </thead>
          <tbody>
            {points.map((point) => (
              <tr key={point.key}>
                <th scope="row">{point.label}</th>
                <td>{point.primary}</td>
                <td>{point.secondary}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}
