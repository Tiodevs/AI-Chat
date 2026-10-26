import { readFileSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { describe, expect, it } from "vitest"

import {
  ContrastError,
  assertContrast,
  contrastRatio,
  parseColorTokens,
  textPairs,
} from "./contrast.ts"

const tokensPath = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "tokens.css",
)

describe("contraste dos tokens", () => {
  it("mantém cada par de texto e fundo em pelo menos 4,5:1", () => {
    const colors = parseColorTokens(readFileSync(tokensPath, "utf8"))
    expect(() => {
      assertContrast(textPairs, colors)
    }).not.toThrow()
  })

  it("falha quando um par fica abaixo de 4,5:1", () => {
    expect(() => {
      assertContrast([["axis", "card"]], {
        axis: "#737373",
        card: "#171717",
      })
    }).toThrow(ContrastError)
    expect(contrastRatio("#737373", "#171717")).toBeLessThan(4.5)
  })
})
