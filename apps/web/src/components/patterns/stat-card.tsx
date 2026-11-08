/**
 * Card de indicador, como Leads e Conversion Rate da imagem de
 * referência: legenda, número grande e variação (seção 14.6).
 *
 * Aparece na linha de quatro indicadores da visão geral (`/admin`):
 * Perguntas, Taxa de respostas, Taxa de abstenção e Taxa de útil, nos
 * últimos 7 dias contra os 7 anteriores (seção 15.5). Quatro por linha no
 * desktop, dois no tablet e um no celular (seção 14.5), pela grade da
 * tela.
 *
 * Estados: carregando (skeletons no formato do número e do selo), sem
 * dados (`emptyText` no lugar do número) e com valor.
 *
 * Acessibilidade: o card é um `group` com `aria-label` de frase inteira,
 * como "Perguntas: 1.234. Alta de 23,4%"; as partes visíveis ficam
 * `aria-hidden`. Assim, a contagem que sobe na tela não é lida número a
 * número.
 *
 * Movimento: M2 (seção 16.3), o preset `countUp`: o número visível sobe
 * de 0 ao valor, com `snap` na casa decimal pedida. Com movimento
 * reduzido, o valor final aparece direto. Usa `text-metric` com
 * `tabular-nums` (seção 14.3).
 */
import { useRef } from "react"

import { Card } from "@/components/ui/card.tsx"
import { Skeleton } from "@/components/ui/skeleton.tsx"
import { useGSAP } from "@/motion/gsap.ts"
import { useMotion } from "@/motion/MotionProvider.tsx"
import { presets } from "@/motion/presets.ts"

import { DeltaBadge, type DeltaDirection } from "./delta-badge.tsx"

/**
 * Indicador grande com legenda e variação. M2: o número visível sobe até o valor,
 * e o valor final fica no aria-label desde o início. SDD 14.6 e 16.3.
 */
export function StatCard({
  label,
  value,
  format,
  decimals = 0,
  delta,
  goodWhen = "up",
  caption,
  emptyText,
  ariaLabel,
  loading = false,
}: {
  label: string
  /** Valor atual; `null` quando não há dado no período. */
  value: number | null
  /** Formata o número na tela, a cada quadro da contagem. */
  format: (value: number) => string
  /** Casas decimais do `snap` da contagem; as taxas usam 3. */
  decimals?: number
  delta: { direction: DeltaDirection; text: string }
  goodWhen?: "up" | "down"
  /** Legenda ao lado do selo, como o período comparado. */
  caption?: string
  emptyText: string
  /** Frase que o leitor de tela lê no lugar das partes visíveis. */
  ariaLabel: string
  loading?: boolean
}) {
  const rootRef = useRef<HTMLDivElement>(null)
  const numberRef = useRef<HTMLSpanElement>(null)
  const { reduced } = useMotion()

  // M2. Roda de novo quando o valor chega ou muda, como na troca de
  // período; o preset escreve o texto do `span` a cada quadro.
  useGSAP(
    () => {
      if (loading || value == null || !numberRef.current) {
        return
      }
      presets.countUp(numberRef.current, reduced, value, format, decimals)
    },
    { dependencies: [value, loading, reduced], scope: rootRef },
  )

  return (
    <Card ref={rootRef} className="gap-3 px-5 py-5" role="group" aria-label={ariaLabel}>
      <p className="text-label text-muted-foreground" aria-hidden="true">
        {label}
      </p>
      {loading ? (
        <Skeleton className="h-9 w-24" />
      ) : (
        <span
          ref={numberRef}
          aria-hidden="true"
          data-stat-value
          className="text-metric text-foreground-strong tabular-nums"
        >
          {value == null ? emptyText : format(value)}
        </span>
      )}
      <div className="flex flex-wrap items-center gap-2" aria-hidden="true">
        {loading ? <Skeleton className="h-5 w-28" /> : <DeltaBadge {...delta} goodWhen={goodWhen} />}
        {caption ? <span className="text-caption text-subtle-foreground">{caption}</span> : null}
      </div>
    </Card>
  )
}
