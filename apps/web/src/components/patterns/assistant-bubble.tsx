import { useRef } from "react"

import { StreamingCaret } from "@/components/patterns/streaming-caret.tsx"
import { pt } from "@/i18n/pt.ts"
import { useGSAP } from "@/motion/gsap.ts"
import { useMotion } from "@/motion/MotionProvider.tsx"
import { presets } from "@/motion/presets.ts"

/** Fala do assistente numa conversa guiada, com avatar e balão. */
export function AssistantBubble({
  text,
  typing = false,
}: {
  text?: string
  typing?: boolean
}) {
  const ref = useRef<HTMLDivElement>(null)
  const { reduced } = useMotion()

  useGSAP(
    () => {
      presets.enterAssistant(ref.current, reduced)
    },
    { scope: ref }
  )

  return (
    <div ref={ref} className="flex items-end gap-2" aria-busy={typing || undefined}>
      <span
        aria-hidden="true"
        className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-caption font-medium text-primary-foreground"
      >
        A
      </span>
      <div className="flex max-w-[85%] flex-col gap-1">
        <span className="sr-only">{pt.registration.assistantName}</span>
        <div className="rounded-2xl rounded-bl-md border border-border bg-muted px-4 py-3 text-message text-foreground">
          {typing ? (
            <span className="flex items-center gap-2 text-muted-foreground">
              {pt.registration.typing}
              <StreamingCaret />
            </span>
          ) : (
            <p className="whitespace-pre-wrap">{text}</p>
          )}
        </div>
      </div>
    </div>
  )
}
