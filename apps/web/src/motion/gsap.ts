import { useGSAP } from "@gsap/react"
import gsap from "gsap"
import { Flip } from "gsap/Flip"

import { motionTokens } from "./tokens.ts"

gsap.registerPlugin(useGSAP, Flip)
gsap.defaults({
  duration: motionTokens.duration.base,
  ease: motionTokens.ease.enter,
})

export { Flip, gsap, useGSAP }
