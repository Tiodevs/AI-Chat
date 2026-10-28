import { useRef } from "react"

import { useGSAP } from "@/motion/gsap.ts"
import { useMotion } from "@/motion/MotionProvider.tsx"
import { presets } from "@/motion/presets.ts"

export function StreamingCaret() {
  const ref = useRef<HTMLSpanElement>(null)
  const { reduced } = useMotion()

  useGSAP(
    () => {
      presets.pulseCaret(ref.current, reduced)
    },
    { scope: ref }
  )

  return (
    <span
      ref={ref}
      data-caret
      aria-hidden="true"
      className="ms-0.5 inline-block h-[1em] w-0.5 bg-foreground align-middle"
    />
  )
}
