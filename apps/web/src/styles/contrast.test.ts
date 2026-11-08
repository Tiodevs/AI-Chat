/**
 * Cada par de token de texto e de fundo passa no contraste AA de 4,5:1.
 * NFR-14, seções 14.2 e 21.1 do SDD.
 *
 * Lê `tokens.css` do disco e confere os pares de `textPairs`, de
 * `contrast.ts`: cada token de texto sobre cada superfície, mais o
 * `--primary-foreground` sobre o `--primary`. O segundo teste prova que a
 * conferência falha com o cinza dos eixos da imagem de referência sobre o
 * `--card`, que dá 3,8:1 (ajuste de contraste da seção 14.2). Roda no projeto
 * `dom` do Vitest. Não usa a API nem banco.
 */
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

/** Caminho de `tokens.css`, ao lado deste arquivo. */
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
