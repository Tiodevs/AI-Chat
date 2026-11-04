import { useRef, useState } from "react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card.tsx"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs.tsx"
import { useGSAP } from "@/motion/gsap.ts"
import { useMotion } from "@/motion/MotionProvider.tsx"
import { presets } from "@/motion/presets.ts"
import { cn } from "@/lib/utils.ts"

import { StatTile } from "./stat-tile.tsx"
import { toneDot, type Tone } from "./tone.ts"

export type StatusSegment = { key: string; label: string; count: number; tone: Tone }
export type StatusView = { key: string; label: string; segments: StatusSegment[] }

const percent = new Intl.NumberFormat("pt-BR", { style: "percent", maximumFractionDigits: 0 })
const count = new Intl.NumberFormat("pt-BR")

/**
 * Barra segmentada com abas, como Leads Management na imagem. M15: cada camada muda
 * scaleX até a soma acumulada, sem animar largura. As contagens ficam em texto. SDD 14.6.
 */
export function SegmentedStatusCard({
  title,
  views,
  emptyText,
}: {
  title: string
  views: StatusView[]
  emptyText: string
}) {
  const [active, setActive] = useState(views[0]?.key ?? "")
  const barRef = useRef<HTMLDivElement>(null)
  const { reduced } = useMotion()
  const view = views.find((item) => item.key === active) ?? views[0]
  const segments = view?.segments ?? []
  const total = segments.reduce((sum, segment) => sum + segment.count, 0)
  const layers = segments.map((segment, index) => {
    const upTo = segments.slice(0, index + 1).reduce((sum, item) => sum + item.count, 0)
    return { ...segment, scale: total > 0 ? upTo / total : 0 }
  })
  const signature = layers.map((layer) => layer.scale.toFixed(4)).join("|")

  useGSAP(
    () => {
      const bar = barRef.current
      if (!bar) {
        return
      }
      presets.moveSegments(bar.querySelectorAll("[data-segment]"), reduced)
    },
    { dependencies: [signature, reduced], scope: barRef },
  )

  const content = (
    <div className="flex flex-col gap-4">
      <div
        ref={barRef}
        aria-hidden="true"
        className="relative h-2.5 w-full overflow-hidden rounded-full bg-muted"
      >
        {layers.map((layer, index) => (
          <div
            key={layer.key}
            data-segment
            data-scale={layer.scale}
            style={{ zIndex: layers.length - index, transform: "scaleX(0)" }}
            className={cn("absolute inset-0 origin-left", toneDot[layer.tone])}
          />
        ))}
      </div>
      {total === 0 ? (
        <p className="text-body text-muted-foreground">{emptyText}</p>
      ) : (
        <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4" aria-label={view?.label}>
          {segments.map((segment) => (
            <li key={segment.key}>
              <StatTile
                label={segment.label}
                tone={segment.tone}
                value={count.format(segment.count)}
                detail={percent.format(segment.count / total)}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  )

  const heading = (
    <CardTitle>
      <h2 className="text-label text-foreground-strong">{title}</h2>
    </CardTitle>
  )

  if (views.length <= 1) {
    return (
      <Card className="gap-4">
        <CardHeader>{heading}</CardHeader>
        <CardContent>{content}</CardContent>
      </Card>
    )
  }

  return (
    <Card className="gap-4">
      <Tabs value={view?.key} onValueChange={setActive} className="flex flex-col gap-4">
        <CardHeader className="flex flex-wrap items-center justify-between gap-3">
          {heading}
          <TabsList>
            {views.map((item) => (
              <TabsTrigger key={item.key} value={item.key}>
                {item.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </CardHeader>
        <CardContent>
          {views.map((item) => (
            <TabsContent key={item.key} value={item.key}>
              {item.key === view?.key ? content : null}
            </TabsContent>
          ))}
        </CardContent>
      </Tabs>
    </Card>
  )
}
