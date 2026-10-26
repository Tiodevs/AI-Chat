import { ESLint } from "eslint"
import { describe, expect, it } from "vitest"

const root = process.cwd()

async function lint(code: string, filePath: string) {
  const eslint = new ESLint({ cwd: root })
  const results = await eslint.lintText(code, { filePath: `${root}/${filePath}` })
  return results[0]
}

describe("limites de camada do frontend", () => {
  it("falha quando um componente chama fetch", async () => {
    const result = await lint(
      'export function Example() { return <button onClick={() => fetch("/backend/health")} /> }\n',
      "src/components/patterns/Example.tsx",
    )
    expect(result?.errorCount).toBeGreaterThan(0)
    expect(result?.messages.map((message) => message.message).join("\n")).toMatch(
      /fetch/i,
    )
  })

  it("falha quando um componente importa o cliente da API", async () => {
    const result = await lint(
      'import { api } from "@/lib/api"\nexport function Example() { return api }\n',
      "src/components/ui/Example.tsx",
    )
    expect(result?.messages.some((message) => message.ruleId === "no-restricted-imports")).toBe(
      true,
    )
  })

  it("permite o cliente da API num hook de feature, sem fetch direto", async () => {
    const allowed = await lint(
      'import { api } from "@/lib/api"\nexport function useAsk() { return api }\n',
      "src/features/ask/useAsk.ts",
    )
    expect(
      allowed?.messages.filter((message) => message.ruleId === "no-restricted-imports"),
    ).toEqual([])

    const blocked = await lint(
      'export function useAsk() { return fetch("/backend/health") }\n',
      "src/features/ask/useAsk.ts",
    )
    expect(blocked?.errorCount).toBeGreaterThan(0)
  })

  it("permite fetch na biblioteca de transporte", async () => {
    const result = await lint(
      'export function readEvents() { return fetch("/backend/health") }\n',
      "src/lib/sse.ts",
    )
    expect(result?.errorCount).toBe(0)
  })
})
