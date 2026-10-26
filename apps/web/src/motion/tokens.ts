export const motionTokens = {
  duration: {
    instant: 0.12,
    fast: 0.18,
    base: 0.28,
    slow: 0.45,
    chart: 0.8,
  },
  ease: {
    enter: "power2.out",
    exit: "power2.in",
    move: "power3.inOut",
    confirm: "back.out(2)",
  },
  stagger: {
    list: 0.05,
  },
  distance: {
    enter: 8,
  },
} as const
