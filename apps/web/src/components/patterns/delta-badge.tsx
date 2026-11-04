import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react"

import { cn } from "@/lib/utils.ts"

import { toneDot, toneSurface, type Tone } from "./tone.ts"

export type DeltaDirection = "up" | "down" | "flat" | "none"

/** Variação contra o período anterior. Ícone e texto, nunca só a cor. SDD 14.6. */
export function DeltaBadge({
  direction,
  text,
  goodWhen = "up",
}: {
  direction: DeltaDirection
  text: string
  goodWhen?: "up" | "down"
}) {
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
