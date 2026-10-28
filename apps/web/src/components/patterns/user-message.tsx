import { useRef } from "react"

import { pt } from "@/i18n/pt.ts"
import { useGSAP } from "@/motion/gsap.ts"
import { useMotion } from "@/motion/MotionProvider.tsx"
import { presets } from "@/motion/presets.ts"

export function UserMessage({
  text,
  privacy,
}: {
  text: string
  privacy: boolean
}) {
  const ref = useRef<HTMLDivElement>(null)
  const { reduced } = useMotion()

  useGSAP(
    () => {
      presets.enterUserMessage(ref.current, reduced)
    },
    { scope: ref }
  )

  return (
    <div ref={ref} className="flex justify-end">
      <div className="max-w-[85%] rounded-2xl bg-card px-4 py-3 text-message text-foreground">
        <p className="whitespace-pre-wrap">
          {privacy ? pt.ask.privacyNote : text}
        </p>
      </div>
    </div>
  )
}
