import { readdirSync, readFileSync, statSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { describe, expect, it } from "vitest"

const sourceRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..")

const hex = /#[0-9a-fA-F]{3,8}\b/
const palette =
  /\b(?:bg|text|border|fill|stroke|from|to|via|ring|outline|caret|divide|placeholder|decoration|accent)-(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|black|white)(?:-\d{2,3})?(?:\/\d+)?\b/
const colorFunction = /\b(?:rgb|rgba|hsl|hsla|oklch)\(/

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
