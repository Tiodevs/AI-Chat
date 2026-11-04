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
  value: number | null
  format: (value: number) => string
  decimals?: number
  delta: { direction: DeltaDirection; text: string }
  goodWhen?: "up" | "down"
  caption?: string
  emptyText: string
  ariaLabel: string
  loading?: boolean
}) {
  const rootRef = useRef<HTMLDivElement>(null)
  const numberRef = useRef<HTMLSpanElement>(null)
  const { reduced } = useMotion()

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
