/**
 * Card de série no tempo, como Revenue over time da imagem de referência:
 * duas linhas com área, cursor vertical e pílula de data invertida (seção
 * 14.6).
 *
 * Aparece em "Perguntas ao longo do tempo", na visão geral (`/admin`):
 * perguntas e respostas por dia, com o seletor de período (7 ou 30 dias)
 * que vale para a tela toda (seção 15.5). O período vive na tela; o card
 * só avisa a troca por `onPeriodChange`.
 *
 * Acessibilidade: legenda, gráfico e cursor são `aria-hidden`; uma tabela
 * em `sr-only` dá os mesmos números ao leitor de tela (seção 15.8). O
 * seletor de período é um `ToggleGroup` com nome. A camada de
 * acessibilidade do Recharts fica desligada, para nada focável ficar
 * dentro da área escondida.
 *
 * Movimento (seção 16.3), pelos presets:
 * - M3: `revealChart` revela o gráfico da esquerda com `scaleX` em
 *   `duration.chart` (0,8 s), ao montar e quando os dados mudam.
 * - M4: `followPointer` cria funções `gsap.quickTo` em `x` e `y`, de
 *   0,2 s, que levam o cursor e a pílula até o ponteiro.
 * Com movimento reduzido, o gráfico aparece completo e o cursor pula para
 * a posição. A animação do próprio Recharts fica desligada.
 */
import { useRef, useState } from "react"
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card.tsx"
import { ChartContainer, type ChartConfig } from "@/components/ui/chart.tsx"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group.tsx"
import { useGSAP } from "@/motion/gsap.ts"
import { useMotion } from "@/motion/MotionProvider.tsx"
import { presets } from "@/motion/presets.ts"

/** Um dia da série: a linha principal e a secundária. */
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
  /** Nome do seletor de período. */
  periodLabel: string
  periods: { value: string; label: string }[]
  /** Período escolhido, o `value` de um item de `periods`. */
  period: string
  onPeriodChange: (value: string) => void
}) {
  const rootRef = useRef<HTMLDivElement>(null)
  const plotRef = useRef<HTMLDivElement>(null)
  const pointerRef = useRef<HTMLDivElement>(null)
  // Guarda a função de mover do M4 entre renderizações, sem re-renderizar.
  const moveRef = useRef<((x: number, y: number) => void) | null>(null)
  const [hovered, setHovered] = useState<number | null>(null)
  const { reduced } = useMotion()
  // Muda quando chegam outros dias ou outros valores da série principal,
  // e só então M3 revela o gráfico de novo.
  const signature = points.map((point) => `${point.key}:${String(point.primary)}`).join("|")

  // M3 e M4. O `followPointer` é recriado junto, com o movimento atual.
  useGSAP(
    () => {
      presets.revealChart(plotRef.current, reduced)
      moveRef.current = presets.followPointer(pointerRef.current, reduced)
    },
    { dependencies: [signature, reduced], scope: rootRef },
  )

  // As chaves viram `--color-primary` e `--color-secondary` só dentro do
  // gráfico. O nome coincide com o token do tema, sem conflito: com o
  // `@theme inline`, a classe `bg-primary` lê `--primary` direto.
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
          // Clicar no período já ligado faz o Radix mandar `""`; o card
          // ignora, para sempre haver um período escolhido.
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
                // O Recharts entrega o índice do ponto sob o ponteiro e a
                // coordenada x dele. O cursor só anda na horizontal.
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
                {/* Faz o papel do `--chart-area` da seção 14.2, sem usar o */}
                {/* token: a cor da série principal, de 16% a 0 de alfa. */}
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
                  // Tracejada: as duas séries se distinguem também pelo
                  // traço, não só pelo tom de cinza.
                  strokeDasharray="4 4"
                  fill="none"
                  isAnimationActive={false}
                  activeDot={false}
                />
              </AreaChart>
            </ChartContainer>
          </div>
          {/* Cursor do M4: a pílula invertida (`--primary`, seção 14.1) e */}
          {/* a linha em `--ring`. O GSAP move só o `transform`; mostrar e */}
          {/* esconder é o `visibility` do React, fora do preset. */}
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
        {/* A tabela equivalente da seção 15.8, só para o leitor de tela. */}
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
