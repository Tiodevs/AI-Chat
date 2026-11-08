/**
 * Selo de variação de um indicador contra o período anterior, como o
 * "+12%" dos cards Leads e Conversion Rate da imagem de referência.
 *
 * Aparece dentro do `StatCard`, na linha de indicadores de `/admin`
 * (seção 15.5). O tom sai da direção e de `goodWhen`: subir é bom em
 * Perguntas e ruim na Taxa de abstenção. Ponto, seta e texto dizem a
 * mesma coisa, então a cor nunca é o único sinal (seção 15.8). Usa os
 * tons de `tone.ts` e ícones do Lucide com traço 1,75. Seções 14.1 e 14.6.
 */
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react"

import { cn } from "@/lib/utils.ts"

import { toneDot, toneSurface, type Tone } from "./tone.ts"

/**
 * `up` e `down` seguem o sinal da variação; `flat` é "Sem variação", e
 * `none`, "Sem período anterior" para comparar.
 */
export type DeltaDirection = "up" | "down" | "flat" | "none"

/** Variação contra o período anterior. Ícone e texto, nunca só a cor. SDD 14.6. */
export function DeltaBadge({
  direction,
  text,
  goodWhen = "up",
}: {
  direction: DeltaDirection
  /** Texto pronto, como "Alta de 12%". */
  text: string
  /** Direção que é boa para este indicador. */
  goodWhen?: "up" | "down"
}) {
  // Verde quando a direção é a desejada, vermelho quando não é; sem
  // variação ou sem base, neutro.
  const tone: Tone =
    direction === "up" || direction === "down"
      ? direction === goodWhen
        ? "success"
        : "danger"
      : "neutral"
  const Icon = direction === "up" ? ArrowUpRight : direction === "down" ? ArrowDownRight : Minus
  return (
    <span
      data-tone={tone}
      className={cn(
        "inline-flex w-fit items-center gap-1.5 rounded-full px-2 py-0.5 text-caption text-foreground",
        toneSurface[tone],
      )}
    >
      <span aria-hidden="true" className={cn("size-1.5 rounded-full", toneDot[tone])} />
      <Icon className="size-3.5" strokeWidth={1.75} aria-hidden="true" />
      {text}
    </span>
  )
}
