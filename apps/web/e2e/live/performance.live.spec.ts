import { mkdirSync, writeFileSync } from "node:fs"
import { brotliCompressSync, gzipSync } from "node:zlib"

import { pt } from "../../src/i18n/pt.ts"
import { visitingQuestion } from "../api.ts"

import { expect, test } from "./fixtures.ts"

/**
 * Metas de desempenho da seção 5.3 na página inicial. Etapa 9.1, CA-3.
 *
 * Celular emulado (Pixel 5) com a rede do perfil "Slow 4G" do Lighthouse (150 ms de ida e
 * volta, 1,6 Mbps de descida, 750 kbps de subida) e a CPU 4 vezes mais lenta. O `vite preview`
 * não comprime, então o tamanho do JavaScript é medido com gzip no próprio teste; a Vercel
 * entrega com brotli, que fica menor. O resultado vai para `test-results/desempenho.json`.
 */
const budgets = { lcpMs: 2500, cls: 0.1, inpMs: 200, initialJsKb: 200 }

test("a página inicial cumpre LCP, CLS, INP e o orçamento de JavaScript", async ({
  page,
  context,
}) => {
  const cdp = await context.newCDPSession(page)
  await cdp.send("Network.enable")
  await cdp.send("Network.emulateNetworkConditions", {
    offline: false,
    latency: 150,
    downloadThroughput: (1.6 * 1024 * 1024) / 8,
    uploadThroughput: (750 * 1024) / 8,
  })
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 })

  const scripts = new Map<string, number>()
  const brotli = new Map<string, number>()
  page.on("response", async (response) => {
    const request = response.request()
    if (request.resourceType() !== "script" || !response.ok()) {
      return
    }
    try {
      const body = await response.body()
      scripts.set(response.url(), gzipSync(body).length)
      brotli.set(response.url(), brotliCompressSync(body).length)
    } catch {
      // Uma resposta já descartada pelo navegador não conta.
    }
  })

  await page.addInitScript(() => {
    const metrics = { lcp: 0, cls: 0, inp: 0 }
    ;(window as unknown as { __metrics: typeof metrics }).__metrics = metrics
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        metrics.lcp = Math.max(metrics.lcp, entry.startTime)
      }
    }).observe({ type: "largest-contentful-paint", buffered: true })
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries() as (PerformanceEntry & {
        value: number
        hadRecentInput: boolean
      })[]) {
        if (!entry.hadRecentInput) {
          metrics.cls += entry.value
        }
      }
    }).observe({ type: "layout-shift", buffered: true })
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        metrics.inp = Math.max(metrics.inp, entry.duration)
      }
    }).observe({ type: "event", buffered: true, durationThreshold: 16 } as PerformanceObserverInit)
  })

  await page.goto("/")
  await expect(page.getByRole("heading", { name: pt.home.title })).toBeVisible()
  await expect(page.getByLabel(pt.ask.questionLabel)).toBeEditable()
  // O JavaScript inicial é o que chegou até a primeira tela ficar pronta. O que o navegador
  // busca depois, no tempo ocioso (a paleta de comandos), fica de fora.
  const initialScripts = [...scripts.entries()]
  await page.waitForLoadState("networkidle")
  const initialJsKb = initialScripts.reduce((sum, [, bytes]) => sum + bytes, 0) / 1024
  const initialJsBrotliKb =
    initialScripts.reduce((sum, [url]) => sum + (brotli.get(url) ?? 0), 0) / 1024

  // Uma interação típica: abrir o campo e digitar. O INP é a maior latência de evento.
  const composer = page.getByLabel(pt.ask.questionLabel)
  await composer.click()
  await composer.pressSequentially("Qual é o horário")
  await page.getByRole("radio", { name: visitingQuestion().label }).hover()
  await page.waitForTimeout(500)
  const metrics = await page.evaluate(
    () => (window as unknown as { __metrics: { lcp: number; cls: number; inp: number } }).__metrics,
  )

  const result = {
    measuredAt: new Date().toISOString(),
    profile: "Pixel 5, Slow 4G (150 ms, 1,6 Mbps / 750 kbps), CPU 4x",
    lcpMs: Math.round(metrics.lcp),
    cls: Number(metrics.cls.toFixed(3)),
    inpMs: Math.round(metrics.inp),
    initialJsKb: Number(initialJsKb.toFixed(1)),
    initialJsBrotliKb: Number(initialJsBrotliKb.toFixed(1)),
    scripts: initialScripts
      .map(([url, bytes]) => ({ file: new URL(url).pathname, gzipKb: Number((bytes / 1024).toFixed(1)) }))
      .sort((left, right) => right.gzipKb - left.gzipKb),
    budgets,
  }
  mkdirSync("test-results", { recursive: true })
  writeFileSync("test-results/desempenho.json", `${JSON.stringify(result, null, 2)}\n`)
  console.log(JSON.stringify(result, null, 2))

  expect.soft(result.initialJsKb, "JavaScript inicial de / em KB com gzip").toBeLessThanOrEqual(
    budgets.initialJsKb,
  )
  expect.soft(result.lcpMs, "LCP em ms").toBeLessThan(budgets.lcpMs)
  expect.soft(result.cls, "CLS").toBeLessThan(budgets.cls)
  expect.soft(result.inpMs, "maior latência de interação em ms").toBeLessThan(budgets.inpMs)
})
