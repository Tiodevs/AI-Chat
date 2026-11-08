/**
 * Tons de status dos componentes do admin. Só dados: dois mapas de tom
 * para classe do Tailwind, sem componente.
 *
 * Usado por `DeltaBadge`, `StatTile` e `SegmentedStatusCard`. O modelo
 * `features/admin/insights-model.ts` escolhe o tom de cada desfecho e
 * repete o mesmo tipo `Tone`, sem importar este arquivo.
 * `toneDot` dá o ponto colorido e também pinta os segmentos da barra do
 * `SegmentedStatusCard`. `toneSurface` dá o fundo: o par translúcido da
 * seção 14.2, a cor do token a 15% por `color-mix`. `neutral` usa o cinza
 * `--chart-2` no ponto e `--muted` no fundo.
 *
 * As classes ficam escritas por inteiro, para o Tailwind encontrá-las ao
 * varrer o código.
 */
/** Cor só como status: ponto e fundo translúcido do token. SDD 14.1 e 14.2. */
export type Tone = "success" | "warning" | "danger" | "info" | "neutral"

export const toneDot: Record<Tone, string> = {
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  info: "bg-info",
  neutral: "bg-chart-2",
}

export const toneSurface: Record<Tone, string> = {
  success: "bg-[color-mix(in_oklab,var(--success)_15%,transparent)]",
  warning: "bg-[color-mix(in_oklab,var(--warning)_15%,transparent)]",
  danger: "bg-[color-mix(in_oklab,var(--danger)_15%,transparent)]",
  info: "bg-[color-mix(in_oklab,var(--info)_15%,transparent)]",
  neutral: "bg-muted",
}
