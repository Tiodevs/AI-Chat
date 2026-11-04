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
