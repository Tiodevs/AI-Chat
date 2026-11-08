/**
 * Bloco de contagem, como Open e In Progress da imagem de referência
 * (seção 14.6).
 *
 * Aparece abaixo da barra do `SegmentedStatusCard` (`/admin` e
 * `/admin/quality`), uma por segmento, com a contagem e a porcentagem, e
 * nas três contagens do topo de `/admin/privacy`: atrasados, abertos e em
 * andamento (seção 15.5). A seção 14.6 cita Documentos, mas a tela de
 * documentos não o usa.
 *
 * O ponto colorido é `aria-hidden`: o rótulo em texto diz o que é a
 * contagem, e a cor só reforça (seção 15.8). Número em `tabular-nums`,
 * para não pular quando muda (seção 14.3).
 */
import { cn } from "@/lib/utils.ts"

import { toneDot, type Tone } from "./tone.ts"

/** Bloco de contagem, como Ready e Processing na imagem. SDD 14.6. */
export function StatTile({
  label,
  value,
  detail,
  tone = "neutral",
}: {
  label: string
  /** Contagem já formatada, como "1.234". */
  value: string
  /** Texto menor ao lado do valor, como a porcentagem. */
  detail?: string
  tone?: Tone
}) {
  return (
    <div className="flex min-w-0 flex-col gap-1 rounded-lg bg-muted px-3 py-2.5">
      <span className="flex items-center gap-2 text-caption text-muted-foreground">
        <span aria-hidden="true" className={cn("size-2 shrink-0 rounded-full", toneDot[tone])} />
        <span className="truncate">{label}</span>
      </span>
      <span className="text-body font-medium text-foreground-strong tabular-nums">
        {value}
        {detail ? (
          <span className="ml-1.5 text-caption font-normal text-subtle-foreground">{detail}</span>
        ) : null}
      </span>
    </div>
  )
}
