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
  onComplete?: () => void,
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
  onComplete?: () => void,
) {
  enter(
    target,
    reduced,
    { autoAlpha: 0, y: motionTokens.distance.enter },
    { autoAlpha: 1, y: 0 },
    onComplete,
  )
}

export function showSidebarLabels(
  target: gsap.TweenTarget,
  reduced: boolean,
  visible = true,
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
  })
}

export function enterPresence(target: gsap.TweenTarget, reduced: boolean) {
  enter(
    target,
    reduced,
    { autoAlpha: 0, scale: 0.98 },
    { autoAlpha: 1, scale: 1 },
  )
}

export function exitPresence(
  target: gsap.TweenTarget,
  reduced: boolean,
  onComplete?: () => void,
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
    },
  )
}

export const presets = {
  enterRoute,
  showSidebarLabels,
  enterPresence,
  exitPresence,
  press,
}
