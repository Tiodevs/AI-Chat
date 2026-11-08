/**
 * Cor crua só aparece em `styles/tokens.css`; o resto de `src` usa os tokens
 * semânticos. Seções 14.2 e 14.8 do SDD.
 *
 * Varre os `.ts`, `.tsx` e `.css` de `src`, fora os arquivos de teste e o
 * próprio `tokens.css`, e procura em cada linha, comentários inclusive, três
 * padrões: cor hexadecimal, classe de cor da paleta do Tailwind e as funções
 * de cor rgb, rgba, hsl, hsla e oklch. Por isso nenhum comentário de `src`
 * escreve esses padrões. A falha lista arquivo, linha e texto. Roda no
 * projeto `dom` do Vitest. Não usa a API nem banco.
 */
import { readdirSync, readFileSync, statSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { describe, expect, it } from "vitest"

/** A pasta `src`, um nível acima de `styles`. */
const sourceRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..")

const hex = /#[0-9a-fA-F]{3,8}\b/
const palette =
  /\b(?:bg|text|border|fill|stroke|from|to|via|ring|outline|caret|divide|placeholder|decoration|accent)-(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|black|white)(?:-\d{2,3})?(?:\/\d+)?\b/
const colorFunction = /\b(?:rgb|rgba|hsl|hsla|oklch)\(/

/** Lista todos os arquivos de `directory`, descendo pelas subpastas. */
function filesIn(directory: string): string[] {
  return readdirSync(directory).flatMap((entry) => {
    const path = join(directory, entry)
    if (statSync(path).isDirectory()) {
      return filesIn(path)
    }
    return [path]
  })
}

describe("cores cruas", () => {
  it("só aparecem nos tokens", () => {
    const offenders: string[] = []
    for (const path of filesIn(sourceRoot)) {
      if (!/\.(?:ts|tsx|css)$/.test(path)) {
        continue
      }
      if (
        path.endsWith(".test.ts") ||
        path.endsWith(".test.tsx") ||
        path.endsWith(`${join("styles", "tokens.css")}`)
      ) {
        continue
      }
      const lines = readFileSync(path, "utf8").split("\n")
      lines.forEach((line, index) => {
        if (hex.test(line) || palette.test(line) || colorFunction.test(line)) {
          offenders.push(`${path}:${index + 1}: ${line.trim()}`)
        }
      })
    }
    expect(offenders).toEqual([])
  })
})
