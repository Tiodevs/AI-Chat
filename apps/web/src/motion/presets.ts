import { gsap } from "./gsap.ts"
import { motionTokens } from "./tokens.ts"

function canAnimate(target: gsap.TweenTarget) {
  if (typeof target === "string") {
    return target.length > 0
  }
  if (Array.isArray(target)) {
    return target.length > 0
  }
  if (typeof NodeList !== "undefined" && target instanceof NodeList) {
    return target.length > 0
  }
  return target != null
}

function enter(
  target: gsap.TweenTarget,
  reduced: boolean,
  from: gsap.TweenVars,
  to: gsap.TweenVars,
  onComplete?: () => void
) {
  if (!canAnimate(target)) {
    onComplete?.()
    return
  }
  if (reduced) {
    gsap.set(target, { ...to, autoAlpha: 1 })
    onComplete?.()
    return
  }
  gsap.set(target, { willChange: "transform" })
  gsap.fromTo(target, from, {
    ...to,
    duration: motionTokens.duration.base,
    ease: motionTokens.ease.enter,
    stagger: motionTokens.stagger.list,
    clearProps: "transform,opacity,visibility,will-change",
    onComplete,
  })
}

export function enterRoute(
  target: gsap.TweenTarget,
  reduced: boolean,
  onComplete?: () => void
) {
  enter(
    target,
    reduced,
    { autoAlpha: 0, y: motionTokens.distance.enter },
    { autoAlpha: 1, y: 0 },
    onComplete
  )
}

export function showSidebarLabels(
  target: gsap.TweenTarget,
  reduced: boolean,
  visible = true
) {
  if (!canAnimate(target)) {
    return
  }
  if (reduced) {
    gsap.set(target, { autoAlpha: visible ? 1 : 0 })
    return
  }
  gsap.to(target, {
    autoAlpha: visible ? 1 : 0,
    duration: motionTokens.duration.fast,
    ease: visible ? motionTokens.ease.enter : motionTokens.ease.exit,
    overwrite: "auto",
    clearProps: visible ? "opacity,visibility" : undefined,
  })
}

export function enterPresence(target: gsap.TweenTarget, reduced: boolean) {
  enter(
    target,
    reduced,
    { autoAlpha: 0, scale: 0.98 },
    { autoAlpha: 1, scale: 1 }
  )
}

export function enterFromSide(
  target: gsap.TweenTarget,
  reduced: boolean,
  distance = 20
) {
  enter(
    target,
    reduced,
    { autoAlpha: 0, x: -Math.abs(distance) },
    { autoAlpha: 1, x: 0 }
  )
}

export function exitPresence(
  target: gsap.TweenTarget,
  reduced: boolean,
  onComplete?: () => void
) {
  if (!canAnimate(target)) {
    onComplete?.()
    return
  }
  if (reduced) {
    gsap.set(target, { autoAlpha: 0, scale: 1 })
    onComplete?.()
    return
  }
  gsap.to(target, {
    autoAlpha: 0,
    duration: motionTokens.duration.fast,
    ease: motionTokens.ease.exit,
    onComplete,
  })
}

export function exitToSide(
  target: gsap.TweenTarget,
  reduced: boolean,
  onComplete?: () => void,
  distance = 20
) {
  if (!canAnimate(target)) {
    onComplete?.()
    return
  }
  if (reduced) {
    gsap.set(target, { autoAlpha: 0, x: 0 })
    onComplete?.()
    return
  }
  gsap.to(target, {
    autoAlpha: 0,
    x: -Math.abs(distance),
    duration: motionTokens.duration.fast,
    ease: motionTokens.ease.exit,
    onComplete,
  })
}

const caretPulseSeconds = 0.6
const citationStagger = 0.04
const userEnterDistance = 6

function fadeIn(
  target: gsap.TweenTarget,
  reduced: boolean,
  from: gsap.TweenVars,
  to: gsap.TweenVars,
  options?: { duration?: number; stagger?: number; onComplete?: () => void }
) {
  if (!canAnimate(target)) {
    options?.onComplete?.()
    return
  }
  if (reduced) {
    gsap.set(target, { ...to, autoAlpha: 1 })
    options?.onComplete?.()
    return
  }
  gsap.set(target, { willChange: "transform" })
  gsap.fromTo(target, from, {
    ...to,
    duration: options?.duration ?? motionTokens.duration.base,
    ease: motionTokens.ease.enter,
    stagger: options?.stagger,
    clearProps: "transform,opacity,visibility,will-change",
    onComplete: options?.onComplete,
  })
}

export function enterUserMessage(
  target: gsap.TweenTarget,
  reduced: boolean,
  onComplete?: () => void
) {
  fadeIn(
    target,
    reduced,
    { autoAlpha: 0, y: userEnterDistance },
    { autoAlpha: 1, y: 0 },
    { onComplete }
  )
}

export function enterAssistant(
  target: gsap.TweenTarget,
  reduced: boolean,
  onComplete?: () => void
) {
  fadeIn(target, reduced, { autoAlpha: 0 }, { autoAlpha: 1 }, { onComplete })
}

export function pulseCaret(target: gsap.TweenTarget, reduced: boolean) {
  if (!canAnimate(target)) {
    return
  }
  if (reduced) {
    gsap.set(target, { opacity: 1 })
    return
  }
  gsap.to(target, {
    opacity: 0.3,
    duration: caretPulseSeconds,
    repeat: -1,
    yoyo: true,
  })
}

export function enterCitations(
  target: gsap.TweenTarget,
  reduced: boolean,
  onComplete?: () => void
) {
  fadeIn(
    target,
    reduced,
    { autoAlpha: 0, scale: 0.9 },
    { autoAlpha: 1, scale: 1 },
    { stagger: citationStagger, onComplete }
  )
}

export function replaceAnswer(
  target: gsap.TweenTarget,
  reduced: boolean,
  onComplete?: () => void
) {
  const root = target instanceof Element ? target : null
  const outgoing = root?.querySelector("[data-outgoing]") ?? null
  const incoming = root?.querySelector("[data-incoming]") ?? null
  if (reduced) {
    if (outgoing) {
      gsap.set(outgoing, { autoAlpha: 0 })
    }
    if (incoming) {
      gsap.set(incoming, { autoAlpha: 1 })
    }
    if (!outgoing && !incoming) {
      gsap.set(target, { autoAlpha: 1 })
    }
    onComplete?.()
    return
  }
  if (!outgoing || !incoming) {
    fadeIn(target, false, { autoAlpha: 0 }, { autoAlpha: 1 }, { onComplete })
    return
  }
  const timeline = gsap.timeline({ onComplete })
  timeline.to(outgoing, {
    autoAlpha: 0,
    duration: motionTokens.duration.fast,
    ease: motionTokens.ease.exit,
  })
  timeline.fromTo(
    incoming,
    { autoAlpha: 0 },
    {
      autoAlpha: 1,
      duration: motionTokens.duration.base,
      ease: motionTokens.ease.enter,
      clearProps: "opacity,visibility",
    },
    ">"
  )
}

export function press(target: gsap.TweenTarget, reduced: boolean) {
  if (!canAnimate(target)) {
    return
  }
  if (reduced) {
    gsap.set(target, { scale: 1 })
    return
  }
  gsap.fromTo(
    target,
    { scale: 0.98 },
    {
      scale: 1,
      duration: motionTokens.duration.instant,
      ease: motionTokens.ease.enter,
      clearProps: "transform",
    }
  )
}

export const presets = {
  enterRoute,
  showSidebarLabels,
  enterPresence,
  enterFromSide,
  exitPresence,
  exitToSide,
  enterUserMessage,
  enterAssistant,
  pulseCaret,
  enterCitations,
  replaceAnswer,
  press,
}
