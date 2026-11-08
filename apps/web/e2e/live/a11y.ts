/**
 * Helpers de acessibilidade da suíte ao vivo: alvos de toque e foco pelo
 * teclado. NFR-14 e seção 15.8 do SDD.
 *
 * O `audit.live.spec.ts` mede os alvos com `smallTargets`, e o
 * `keyboard.live.spec.ts` anda pela página com `tabTo`. Os dois rodam na
 * página aberta e não chamam a API.
 */
import { expect, type Page } from "@playwright/test"

/** Um alvo abaixo do mínimo: o elemento e o tamanho medido, em px. */
export type SmallTarget = { name: string; width: number; height: number }

/**
 * Alvos de toque da seção 15.8: 44 por 44 px no celular e 24 por 24 px no desktop.
 *
 * Fica de fora o que o WCAG 2.2 (2.5.8) também deixa de fora: link dentro de uma frase, que
 * segue o tamanho do texto, e o que está escondido para leitores de tela (`sr-only`), como o
 * link de pular para o conteúdo antes de receber o foco.
 *
 * Devolve os alvos visíveis abaixo de `minimum` px, com a área do rótulo
 * somada à do controle.
 */
export async function smallTargets(page: Page, minimum: number): Promise<SmallTarget[]> {
  return page.evaluate((min) => {
    const selector = [
      "a[href]",
      "button",
      "input:not([type=hidden])",
      "select",
      "textarea",
      "[role=button]",
      "[role=radio]",
      "[role=tab]",
      "[role=switch]",
      "[role=checkbox]",
      "[role=menuitem]",
      "[role=option]",
    ].join(",")
    const found: { name: string; width: number; height: number }[] = []
    for (const element of Array.from(document.querySelectorAll<HTMLElement>(selector))) {
      const style = getComputedStyle(element)
      const box = element.getBoundingClientRect()
      if (style.visibility === "hidden" || style.display === "none" || box.width <= 1 || box.height <= 1) {
        continue
      }
      if (element.closest("[aria-hidden=true], [inert]")) {
        continue
      }
      // Alvo dentro de uma frase segue o tamanho do texto (exceção do WCAG 2.5.8): um link
      // num parágrafo ou num rótulo, ou o marcador de fonte no meio da resposta.
      // Botão de tabela não é frase: só o link puramente inline conta em células e listas.
      const inSentence =
        (style.display === "inline" && element.closest("p, li, dd, td, label") !== null) ||
        (style.display.startsWith("inline") && element.closest("p, label") !== null)
      if (inSentence) {
        continue
      }
      // O rótulo de um controle também recebe o toque: o alvo é o controle somado ao rótulo.
      let target = { left: box.left, top: box.top, right: box.right, bottom: box.bottom }
      const labels = [
        ...(element.id ? Array.from(document.querySelectorAll<HTMLElement>(`label[for="${CSS.escape(element.id)}"]`)) : []),
        ...(element instanceof HTMLInputElement && element.closest("label") ? [element.closest("label") as HTMLElement] : []),
      ]
      for (const label of labels) {
        const area = label.getBoundingClientRect()
        target = {
          left: Math.min(target.left, area.left),
          top: Math.min(target.top, area.top),
          right: Math.max(target.right, area.right),
          bottom: Math.max(target.bottom, area.bottom),
        }
      }
      const width = target.right - target.left
      const height = target.bottom - target.top
      if (Math.round(width) < min || Math.round(height) < min) {
        const name =
          element.getAttribute("aria-label") ??
          (element.textContent ?? "").trim().slice(0, 60) ??
          element.tagName
        found.push({
          name: `${element.tagName.toLowerCase()} "${name || element.getAttribute("name") || element.id}"`,
          width: Math.round(width),
          height: Math.round(height),
        })
      }
    }
    return found
  }, minimum)
}

/**
 * Falha se algum alvo fica abaixo de 44 px numa tela com menos de 768 px de
 * largura, ou de 24 px nas outras. Nenhum spec o usa hoje: o
 * `audit.live.spec.ts` chama `smallTargets` com `expect.soft`.
 */
export async function expectTouchTargets(page: Page) {
  const width = page.viewportSize()?.width ?? 1280
  const minimum = width < 768 ? 44 : 24
  expect(await smallTargets(page, minimum), `alvos menores que ${String(minimum)} px`).toEqual([])
}

/** Aperta Tab até o foco chegar ao alvo. Falha se o alvo não é alcançável pelo teclado. */
export async function tabTo(page: Page, target: ReturnType<Page["locator"]>, limit = 60) {
  for (let step = 0; step < limit; step += 1) {
    if (await target.evaluate((element) => element === document.activeElement)) {
      return
    }
    await page.keyboard.press("Tab")
  }
  throw new Error(`O teclado não alcançou o alvo em ${String(limit)} Tabs.`)
}
