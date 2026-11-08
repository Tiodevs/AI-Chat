/**
 * Moldura de gráfico do shadcn/ui sobre o Recharts. Não usa Radix.
 *
 * Usada pelo `TrendChartCard` e pelo `GroupedBarCard` na visão geral do
 * admin (`/admin`). O Recharts só é baixado nas rotas de admin (seção
 * 13.1).
 *
 * O `ChartContainer` recebe um `ChartConfig` com o rótulo e a cor de cada
 * série, gera as variáveis `--color-<série>` num `<style>` só deste
 * gráfico e pinta eixos, grade e cursor com tokens (`fill-muted-foreground`,
 * `stroke-border`, `fill-muted`).
 *
 * O que o projeto mudou: o shadcn pinta a grade e os pontos filtrando pelo
 * atributo `stroke` com a cor crua padrão do Recharts. O teste de cores
 * cruas (`styles/raw-color.test.ts`) barra cor em hexadecimal no código,
 * então aqui o seletor vale para toda linha de grade, todo ponto e todo
 * setor. Também saiu o `"use client"`, e o `cn` vem do pacote `cn`.
 *
 * `ChartTooltip`, `ChartTooltipContent`, `ChartLegend` e
 * `ChartLegendContent` vieram do modelo e não têm uso: os cartões desenham
 * a própria legenda e o próprio cursor (M4). Seções 14.6 e 15.8.
 */
import * as React from "react"
import { cn } from "cn"
import * as RechartsPrimitive from "recharts"
import type { TooltipValueType } from "recharts"

// Format: { THEME_NAME: CSS_SELECTOR }
// O `index.html` põe `class="dark"` na raiz, então vale sempre o `.dark`.
const THEMES = { light: "", dark: ".dark" } as const

// Tamanho do primeiro desenho, antes de o `ResponsiveContainer` medir o pai.
const INITIAL_DIMENSION = { width: 320, height: 200 } as const
type TooltipNameType = number | string

/**
 * Configuração das séries: para cada chave do dado (`primary`, `first`),
 * o rótulo, um ícone opcional e a cor. A cor vem como `color` única ou
 * como `theme`, uma por tema. Os cartões passam `var(--chart-N)`, os
 * tokens de série da seção 14.2.
 */
export type ChartConfig = Record<
  string,
  {
    label?: React.ReactNode
    icon?: React.ComponentType
  } & (
    | { color?: string; theme?: never }
    | { color?: never; theme: Record<keyof typeof THEMES, string> }
  )
>

type ChartContextProps = {
  config: ChartConfig
}

const ChartContext = React.createContext<ChartContextProps | null>(null)

/** Lê o `ChartConfig` do `ChartContainer` mais próximo. Fora dele, falha. */
function useChart() {
  const context = React.useContext(ChartContext)

  if (!context) {
    throw new Error("useChart must be used within a <ChartContainer />")
  }

  return context
}

/**
 * Contêiner do gráfico.
 *
 * 1. Gera o id do gráfico com o `useId`, sem os dois-pontos, que não
 *    cabem num seletor de atributo sem aspas, e o põe em `data-chart`.
 * 2. Injeta o `ChartStyle` com as cores das séries.
 * 3. Embrulha o gráfico no `ResponsiveContainer` do Recharts, que mede o
 *    pai e repassa largura e altura ao gráfico. Por isso o chamador dá a
 *    altura (`h-56`) e troca o `aspect-video` por `aspect-auto`.
 */
function ChartContainer({
  id,
  className,
  children,
  config,
  initialDimension = INITIAL_DIMENSION,
  ...props
}: React.ComponentProps<"div"> & {
  config: ChartConfig
  children: React.ComponentProps<
    typeof RechartsPrimitive.ResponsiveContainer
  >["children"]
  initialDimension?: {
    width: number
    height: number
  }
}) {
  // 1.
  const uniqueId = React.useId()
  const chartId = `chart-${id ?? uniqueId.replace(/:/g, "")}`

  return (
    <ChartContext.Provider value={{ config }}>
      <div
        data-slot="chart"
        data-chart={chartId}
        // Os seletores `[&_.recharts-...]` alcançam as classes que o
        // Recharts põe no SVG e trocam as cores padrão por tokens.
        className={cn(
          "flex aspect-video justify-center text-xs [&_.recharts-cartesian-axis-tick_text]:fill-muted-foreground [&_.recharts-cartesian-grid_line]:stroke-border/50 [&_.recharts-curve.recharts-tooltip-cursor]:stroke-border [&_.recharts-dot]:stroke-transparent [&_.recharts-layer]:outline-hidden [&_.recharts-polar-grid_*]:stroke-border [&_.recharts-radial-bar-background-sector]:fill-muted [&_.recharts-rectangle.recharts-tooltip-cursor]:fill-muted [&_.recharts-reference-line_line]:stroke-border [&_.recharts-sector]:outline-hidden [&_.recharts-sector]:stroke-transparent [&_.recharts-surface]:outline-hidden",
          className
        )}
        {...props}
      >
        {/* 2. */}
        <ChartStyle id={chartId} config={config} />
        {/* 3. */}
        <RechartsPrimitive.ResponsiveContainer
          initialDimension={initialDimension}
        >
          {children}
        </RechartsPrimitive.ResponsiveContainer>
      </div>
    </ChartContext.Provider>
  )
}

/**
 * Escreve, para cada tema de `THEMES`, as regras `--color-<série>: <cor>`
 * sob `[data-chart=<id>]`. Assim as séries usam `var(--color-first)` sem
 * vazar para outro gráfico. Por ser um `<style>` em linha, depende do
 * `style-src 'unsafe-inline'` da política de segurança da seção 13.4.
 */
const ChartStyle = ({ id, config }: { id: string; config: ChartConfig }) => {
  const colorConfig = Object.entries(config).filter(
    ([, config]) => config.theme ?? config.color
  )

  if (!colorConfig.length) {
    return null
  }

  return (
    <style
      dangerouslySetInnerHTML={{
        __html: Object.entries(THEMES)
          .map(
            ([theme, prefix]) => `
${prefix} [data-chart=${id}] {
${colorConfig
  .map(([key, itemConfig]) => {
    const color =
      itemConfig.theme?.[theme as keyof typeof itemConfig.theme] ??
      itemConfig.color
    return color ? `  --color-${key}: ${color};` : null
  })
  .join("\n")}
}
`
          )
          .join("\n"),
      }}
    />
  )
}

/** O `Tooltip` do Recharts, reexportado. Sem uso no projeto. */
const ChartTooltip = RechartsPrimitive.Tooltip

/**
 * Conteúdo de tooltip do modelo do shadcn, sem uso no projeto: o
 * `TrendChartCard` desenha a própria pílula de data (M4). Usa
 * `bg-background` e `shadow-xl`, e não o `--popover` e a sombra
 * `shadow-overlay` que a seção 14.4 pede para tooltips.
 */
function ChartTooltipContent({
  active,
  payload,
  className,
  indicator = "dot",
  hideLabel = false,
  hideIndicator = false,
  label,
  labelFormatter,
  labelClassName,
  formatter,
  color,
  nameKey,
  labelKey,
}: React.ComponentProps<typeof RechartsPrimitive.Tooltip> &
  React.ComponentProps<"div"> & {
    hideLabel?: boolean
    hideIndicator?: boolean
    indicator?: "line" | "dot" | "dashed"
    nameKey?: string
    labelKey?: string
  } & Omit<
    RechartsPrimitive.DefaultTooltipContentProps<
      TooltipValueType,
      TooltipNameType
    >,
    "accessibilityLayer"
  >) {
  const { config } = useChart()

  const tooltipLabel = React.useMemo(() => {
    if (hideLabel || !payload?.length) {
      return null
    }

    const [item] = payload
    const key = `${labelKey ?? item?.dataKey ?? item?.name ?? "value"}`
    const itemConfig = getPayloadConfigFromPayload(config, item, key)
    const value =
      !labelKey && typeof label === "string"
        ? (config[label]?.label ?? label)
        : itemConfig?.label

    if (labelFormatter) {
      return (
        <div className={cn("font-medium", labelClassName)}>
          {labelFormatter(value, payload)}
        </div>
      )
    }

    if (!value) {
      return null
    }

    return <div className={cn("font-medium", labelClassName)}>{value}</div>
  }, [
    label,
    labelFormatter,
    payload,
    hideLabel,
    labelClassName,
    config,
    labelKey,
  ])

  if (!active || !payload?.length) {
    return null
  }

  const nestLabel = payload.length === 1 && indicator !== "dot"

  return (
    <div
      className={cn(
        "grid min-w-32 items-start gap-1.5 rounded-lg border border-border/50 bg-background px-2.5 py-1.5 text-xs shadow-xl",
        className
      )}
    >
      {!nestLabel ? tooltipLabel : null}
      <div className="grid gap-1.5">
        {payload
          .filter((item) => item.type !== "none")
          .map((item, index) => {
            const key = `${nameKey ?? item.name ?? item.dataKey ?? "value"}`
            const itemConfig = getPayloadConfigFromPayload(config, item, key)
            const indicatorColor = color ?? item.payload?.fill ?? item.color

            return (
              <div
                key={index}
                className={cn(
                  "flex w-full flex-wrap items-stretch gap-2 [&>svg]:h-2.5 [&>svg]:w-2.5 [&>svg]:text-muted-foreground",
                  indicator === "dot" && "items-center"
                )}
              >
                {formatter && item?.value !== undefined && item.name ? (
                  formatter(item.value, item.name, item, index, item.payload)
                ) : (
                  <>
                    {itemConfig?.icon ? (
                      <itemConfig.icon />
                    ) : (
                      !hideIndicator && (
                        <div
                          className={cn(
                            "shrink-0 rounded-[2px] border-(--color-border) bg-(--color-bg)",
                            {
                              "h-2.5 w-2.5": indicator === "dot",
                              "w-1": indicator === "line",
                              "w-0 border-[1.5px] border-dashed bg-transparent":
                                indicator === "dashed",
                              "my-0.5": nestLabel && indicator === "dashed",
                            }
                          )}
                          style={
                            {
                              "--color-bg": indicatorColor,
                              "--color-border": indicatorColor,
                            } as React.CSSProperties
                          }
                        />
                      )
                    )}
                    <div
                      className={cn(
                        "flex flex-1 justify-between leading-none",
                        nestLabel ? "items-end" : "items-center"
                      )}
                    >
                      <div className="grid gap-1.5">
                        {nestLabel ? tooltipLabel : null}
                        <span className="text-muted-foreground">
                          {itemConfig?.label ?? item.name}
                        </span>
                      </div>
                      {item.value != null && (
                        <span className="font-mono font-medium text-foreground tabular-nums">
                          {typeof item.value === "number"
                            ? item.value.toLocaleString()
                            : String(item.value)}
                        </span>
                      )}
                    </div>
                  </>
                )}
              </div>
            )
          })}
      </div>
    </div>
  )
}

/** A `Legend` do Recharts, reexportada. Sem uso no projeto. */
const ChartLegend = RechartsPrimitive.Legend

/**
 * Legenda do modelo do shadcn, sem uso: os cartões desenham a legenda
 * deles, escondida do leitor de tela, que lê a tabela equivalente.
 */
function ChartLegendContent({
  className,
  hideIcon = false,
  payload,
  verticalAlign = "bottom",
  nameKey,
}: React.ComponentProps<"div"> & {
  hideIcon?: boolean
  nameKey?: string
} & RechartsPrimitive.DefaultLegendContentProps) {
  const { config } = useChart()

  if (!payload?.length) {
    return null
  }

  return (
    <div
      className={cn(
        "flex items-center justify-center gap-4",
        verticalAlign === "top" ? "pb-3" : "pt-3",
        className
      )}
    >
      {payload
        .filter((item) => item.type !== "none")
        .map((item, index) => {
          const key = `${nameKey ?? item.dataKey ?? "value"}`
          const itemConfig = getPayloadConfigFromPayload(config, item, key)

          return (
            <div
              key={index}
              className={cn(
                "flex items-center gap-1.5 [&>svg]:h-3 [&>svg]:w-3 [&>svg]:text-muted-foreground"
              )}
            >
              {itemConfig?.icon && !hideIcon ? (
                <itemConfig.icon />
              ) : (
                <div
                  className="h-2 w-2 shrink-0 rounded-[2px]"
                  style={{
                    backgroundColor: item.color,
                  }}
                />
              )}
              {itemConfig?.label}
            </div>
          )
        })}
    </div>
  )
}

/**
 * Acha a entrada do `ChartConfig` de um item que o Recharts entrega ao
 * tooltip ou à legenda: primeiro pelo valor da chave no item, depois pela
 * própria chave.
 */
function getPayloadConfigFromPayload(
  config: ChartConfig,
  payload: unknown,
  key: string
) {
  if (typeof payload !== "object" || payload === null) {
    return undefined
  }

  const payloadPayload =
    "payload" in payload &&
    typeof payload.payload === "object" &&
    payload.payload !== null
      ? payload.payload
      : undefined

  let configLabelKey: string = key

  if (
    key in payload &&
    typeof payload[key as keyof typeof payload] === "string"
  ) {
    configLabelKey = payload[key as keyof typeof payload] as string
  } else if (
    payloadPayload &&
    key in payloadPayload &&
    typeof payloadPayload[key as keyof typeof payloadPayload] === "string"
  ) {
    configLabelKey = payloadPayload[
      key as keyof typeof payloadPayload
    ] as string
  }

  return configLabelKey in config ? config[configLabelKey] : config[key]
}

export {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  ChartLegend,
  ChartLegendContent,
  ChartStyle,
}
