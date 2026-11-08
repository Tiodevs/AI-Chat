/**
 * As regras de camada do ESLint barram `fetch` e o cliente da API fora do
 * lugar certo. NFR-1, seções 6.2 (teste de arquitetura) e 13.2 do SDD.
 *
 * Roda o ESLint pela API de Node, com o `eslint.config.js` do projeto, sobre
 * trechos de código escritos no teste. Um componente não chama `fetch` nem
 * importa `@/lib/api`; um hook de feature importa o cliente, mas não chama
 * `fetch`; `src/lib` chama `fetch`. É o par do teste de camadas da API em
 * `apps/api/tests/architecture`. Roda no projeto `node` do Vitest, sem jsdom,
 * desde a Etapa 11.1. Não usa a API nem banco.
 */
import { ESLint } from "eslint"
import { describe, expect, it } from "vitest"

/** A pasta `apps/web`, de onde o Vitest roda, com o `eslint.config.js`. */
const root = process.cwd()

/**
 * Passa `code` pelo ESLint como se fosse o arquivo `filePath`, relativo a
 * `apps/web`. O arquivo não precisa existir: o caminho só escolhe os blocos
 * `files` da configuração. Devolve o resultado desse arquivo.
 */
async function lint(code: string, filePath: string) {
  const eslint = new ESLint({ cwd: root })
  const results = await eslint.lintText(code, { filePath: `${root}/${filePath}` })
  return results[0]
}

// O primeiro lint carrega o ESLint a frio; com a suíte inteira em paralelo, passa de 5 s.
describe("limites de camada do frontend", { timeout: 20_000 }, () => {
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
