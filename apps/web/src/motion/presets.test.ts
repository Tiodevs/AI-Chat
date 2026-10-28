import { beforeEach, describe, expect, it, vi } from "vitest"

const set = vi.fn()
const to = vi.fn()
const fromTo = vi.fn()
const timeline = vi.fn(() => ({
  to: vi.fn().mockReturnThis(),
  fromTo: vi.fn().mockReturnThis(),
}))

vi.mock("gsap", () => ({
  default: {
    set,
    to,
    fromTo,
    timeline,
    registerPlugin: vi.fn(),
    defaults: vi.fn(),
    matchMedia: vi.fn(),
    matchMediaRefresh: vi.fn(),
  },
}))

vi.mock("gsap/Flip", () => ({
  Flip: {
    getState: vi.fn(),
    from: vi.fn(),
  },
}))

vi.mock("@gsap/react", () => ({
  useGSAP: () => ({
    contextSafe: (callback: unknown) => callback,
  }),
}))

const { presets } = await import("./presets.ts")

describe("presets com movimento reduzido", () => {
  beforeEach(() => {
    set.mockClear()
    to.mockClear()
    fromTo.mockClear()
  })

  it.each(Object.entries(presets))(
    "%s chama gsap.set e não anima",
    (_name, preset) => {
      preset(document.createElement("div"), true)
      expect(set).toHaveBeenCalled()
      expect(to).not.toHaveBeenCalled()
      expect(fromTo).not.toHaveBeenCalled()
    }
  )

  it("anima a troca de rota quando o movimento está ligado", () => {
    presets.enterRoute(document.createElement("div"), false)
    expect(fromTo).toHaveBeenCalled()
  })

  it("M5 a M9 animam com movimento e ficam diretos quando ele está reduzido", () => {
    const motion = [
      presets.enterUserMessage,
      presets.enterAssistant,
      presets.pulseCaret,
      presets.enterCitations,
      presets.replaceAnswer,
    ]
    for (const preset of motion) {
      set.mockClear()
      to.mockClear()
      fromTo.mockClear()
      timeline.mockClear()
      preset(document.createElement("div"), true)
      expect(set).toHaveBeenCalled()
      expect(to).not.toHaveBeenCalled()
      expect(fromTo).not.toHaveBeenCalled()
      expect(timeline).not.toHaveBeenCalled()
    }
    for (const preset of motion) {
      set.mockClear()
      to.mockClear()
      fromTo.mockClear()
      timeline.mockClear()
      preset(document.createElement("div"), false)
      expect(to.mock.calls.length + fromTo.mock.calls.length).toBeGreaterThan(0)
    }
  })
})
