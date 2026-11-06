import { useGSAP } from "@gsap/react"
import gsap from "gsap"

import { motionTokens } from "./tokens.ts"

gsap.registerPlugin(useGSAP)
gsap.defaults({
  duration: motionTokens.duration.base,
  ease: motionTokens.ease.enter,
})

export { gsap, useGSAP }
