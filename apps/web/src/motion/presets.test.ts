import { beforeEach, describe, expect, it, vi } from "vitest"

const set = vi.fn()
const to = vi.fn()
const fromTo = vi.fn()

vi.mock("gsap", () => ({
  default: {
    set,
    to,
    fromTo,
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
    },
  )

  it("anima a troca de rota quando o movimento está ligado", () => {
    presets.enterRoute(document.createElement("div"), false)
    expect(fromTo).toHaveBeenCalled()
  })
})
