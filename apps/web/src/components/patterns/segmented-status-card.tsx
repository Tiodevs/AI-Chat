/**
 * Card com abas e uma barra segmentada, como Leads Management da imagem
 * de referência (seção 14.6).
 *
 * Aparece no card "Desfechos" de `/admin`, com as abas Desfecho, Intenção
 * e Feedback, e no topo de `/admin/quality` (seção 15.5). Cada aba é uma
 * `StatusView`: uma lista de segmentos com rótulo, contagem e tom. Com
 * uma aba só, o card não mostra abas.
 *
 * Estados: com dados (barra e um `StatTile` por segmento) e vazio
 * (`emptyText`, quando a soma é zero).
 *
 * Acessibilidade: a barra é `aria-hidden`. As contagens e porcentagens
 * ficam em texto, numa lista com o nome da aba, então nada depende da cor
 * ou do desenho (seção 15.8). As abas são o `Tabs` do Radix.
 *
 * Movimento: M15 (seção 16.3), o preset `moveSegments`. Cada segmento é
 * uma camada da largura toda, presa à esquerda, que vai ao `scaleX` da
 * soma acumulada até ele; a camada de antes fica por cima (`zIndex`).
 * Assim cada cor aparece no seu trecho sem animar largura (seção 16.1).
 * Com movimento reduzido, as camadas vão direto à escala.
 */
import { useRef, useState } from "react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card.tsx"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs.tsx"
import { useGSAP } from "@/motion/gsap.ts"
import { useMotion } from "@/motion/MotionProvider.tsx"
import { presets } from "@/motion/presets.ts"
import { cn } from "@/lib/utils.ts"

import { StatTile } from "./stat-tile.tsx"
import { toneDot, type Tone } from "./tone.ts"

/** Um trecho da barra: rótulo, contagem e tom. */
export type StatusSegment = { key: string; label: string; count: number; tone: Tone }
/** Uma aba do card, com os segmentos na ordem da barra. */
export type StatusView = { key: string; label: string; segments: StatusSegment[] }

// Formatadores criados uma vez, fora do componente, no formato pt-BR.
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
  // Escala de cada camada: a soma até ela dividida pelo total. A última
  // camada sempre chega a 1.
  const layers = segments.map((segment, index) => {
    const upTo = segments.slice(0, index + 1).reduce((sum, item) => sum + item.count, 0)
    return { ...segment, scale: total > 0 ? upTo / total : 0 }
  })
  // Só uma mudança de proporção dispara M15 de novo. Na troca de aba, a
  // barra nova monta em `scaleX(0)`; se as duas abas tiverem a mesma
  // assinatura, o efeito não roda e a barra fica vazia.
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
        {/* O preset lê o destino de cada camada em `data-scale`. */}
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

  // Uma aba só não precisa de `Tabs`: o card mostra o conteúdo direto.
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
          {/* Só o painel ativo recebe a barra, para o `barRef` ser único. */}
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
