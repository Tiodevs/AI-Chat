import { useState } from "react"

import { useGSAP } from "./gsap.ts"
import { useMotion } from "./MotionProvider.tsx"
import { presets } from "./presets.ts"

export function useGsapPresence(
  open: boolean,
  ref: { current: HTMLElement | null },
  fromX = 0,
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
      const finish = () => {
        setRendered(false)
      }
      if (open) {
        if (fromX === 0) {
          presets.enterPresence(node, reduced)
        } else {
          presets.enterFromSide(node, reduced, Math.abs(fromX))
        }
        return
      }
      if (fromX === 0) {
        presets.exitPresence(node, reduced, finish)
      } else {
        presets.exitToSide(node, reduced, finish, Math.abs(fromX))
      }
    },
    { dependencies: [open, mounted, reduced, fromX], scope: ref },
  )

  return mounted
}
