import { useState, type RefObject } from "react"

import { useGSAP } from "./gsap.ts"
import { useMotion } from "./MotionProvider.tsx"
import { presets } from "./presets.ts"

export function useGsapPresence(
  open: boolean,
  ref: RefObject<HTMLDivElement | null>,
) {
  const { reduced } = useMotion()
  const [rendered, setRendered] = useState(open)
  const mounted = open || rendered

  useGSAP(
    () => {
      const node = ref.current
      if (!node || !mounted) {
        return
      }
      if (open) {
        presets.enterPresence(node, reduced)
        return
      }
      presets.exitPresence(node, reduced, () => {
        setRendered(false)
      })
    },
    { dependencies: [open, mounted, reduced], scope: ref },
  )

  return mounted
}
