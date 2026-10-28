import { beforeEach, describe, expect, it, vi } from "vitest"

import { motionTokens } from "./tokens.ts"

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

  it("M10 destaca o campo com timeline e fica direto quando o movimento está reduzido", () => {
    const root = document.createElement("div")
    const highlight = document.createElement("div")
    const icon = document.createElement("div")
    highlight.dataset.highlight = "true"
    icon.dataset.confirm = "true"
    root.append(highlight, icon)

    presets.confirmField(root, true)
    expect(set).toHaveBeenCalled()
    expect(timeline).not.toHaveBeenCalled()

    timeline.mockClear()
    presets.confirmField(root, false)
    expect(timeline).toHaveBeenCalled()
    const sequence = timeline.mock.results.at(-1)?.value as {
      fromTo: ReturnType<typeof vi.fn>
    }
    const iconCall = sequence.fromTo.mock.calls.find((call) => {
      const from = call[1] as { scale?: number }
      return from.scale === 0.6
    })
    expect(iconCall?.[2]).toMatchObject({
      scale: 1,
      ease: motionTokens.ease.confirm,
    })
  })

  it("M11 move a barra com scaleX e fica direta quando o movimento está reduzido", () => {
    const bar = document.createElement("div")
    presets.moveStepper(bar, true, 0.5)
    expect(set).toHaveBeenCalledWith(
      bar,
      expect.objectContaining({ scaleX: 0.5 })
    )
    expect(to).not.toHaveBeenCalled()

    presets.moveStepper(bar, false, 0.75)
    expect(to).toHaveBeenCalledWith(
      bar,
      expect.objectContaining({
        scaleX: 0.75,
        ease: motionTokens.ease.move,
        duration: motionTokens.duration.slow,
      })
    )
  })

  it("M12 entrega o foco no fim, com e sem movimento reduzido", () => {
    const card = document.createElement("div")
    const reducedDone = vi.fn()
    presets.enterPassword(card, true, reducedDone)
    expect(set).toHaveBeenCalled()
    expect(fromTo).not.toHaveBeenCalled()
    expect(reducedDone).toHaveBeenCalledOnce()

    const done = vi.fn()
    presets.enterPassword(card, false, done)
    expect(fromTo).toHaveBeenCalledWith(
      card,
      expect.objectContaining({ autoAlpha: 0, y: 12 }),
      expect.objectContaining({
        autoAlpha: 1,
        y: 0,
        duration: motionTokens.duration.slow,
        onComplete: done,
      })
    )
    const vars = fromTo.mock.calls.at(-1)?.[2] as { onComplete?: () => void }
    vars.onComplete?.()
    expect(done).toHaveBeenCalledOnce()
  })
})
