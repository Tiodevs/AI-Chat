/**
 * O cálculo de contraste do WCAG para os pares de texto e fundo dos tokens
 * (seção 14.1, princípio 4, e seção 14.2, ajuste de contraste).
 *
 * Quem usa: só o `contrast.test.ts`. Ele lê `tokens.css`, monta o mapa de
 * tokens com `parseColorTokens` e chama `assertContrast` com `textPairs`:
 * o teste falha se um par ficar abaixo de 4,5:1, o mínimo AA para texto
 * pequeno. Nenhum código do app importa este arquivo.
 */

/** Os fundos onde há texto. */
const surfaces = [
  "shell",
  "background",
  "card",
  "popover",
  "muted",
] as const

/** Os tokens usados como cor de texto, os de status inclusive. */
const texts = [
  "foreground",
  "foreground-strong",
  "muted-foreground",
  "subtle-foreground",
  "success",
  "danger",
  "warning",
  "info",
] as const

/**
 * Os pares conferidos: todo texto sobre todo fundo, mais o texto do botão
 * primário sobre o `primary`. São 41 pares.
 */
export const textPairs: ReadonlyArray<readonly [string, string]> = [
  ...texts.flatMap((text) =>
    surfaces.map((surface) => [text, surface] as const),
  ),
  ["primary-foreground", "primary"],
]

/** O erro que o teste espera: a mensagem lista cada par que falhou. */
export class ContrastError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "ContrastError"
  }
}

/**
 * Converte um canal de 0 a 255 para o valor linear, pela curva do sRGB que
 * a fórmula do WCAG usa.
 */
function channel(value: number) {
  const ratio = value / 255
  if (ratio <= 0.04045) {
    return ratio / 12.92
  }
  return ((ratio + 0.055) / 1.055) ** 2.4
}

/**
 * A luminância relativa do WCAG de uma cor hexadecimal. Só aceita a forma
 * longa, de seis dígitos, a de todos os tokens: a curta, de três, daria um
 * valor errado.
 */
function luminance(hex: string) {
  const value = Number.parseInt(hex.slice(1), 16)
  const red = channel((value >> 16) & 255)
  const green = channel((value >> 8) & 255)
  const blue = channel(value & 255)
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue
}

/**
 * A razão de contraste do WCAG entre duas cores, de 1 a 21: a luminância
 * da mais clara mais 0,05, dividida pela da mais escura mais 0,05. A ordem
 * dos argumentos não muda o resultado.
 */
export function contrastRatio(foreground: string, background: string) {
  const first = luminance(foreground)
  const second = luminance(background)
  const lighter = Math.max(first, second)
  const darker = Math.min(first, second)
  return (lighter + 0.05) / (darker + 0.05)
}

/**
 * Lê cada declaração de variável CSS do texto num mapa de nome para valor.
 * Pega também o que não é cor, como o raio e o gradiente; quem decide o
 * que é cor é `resolveColor`, só nos pares pedidos.
 */
export function parseColorTokens(css: string) {
  const colors: Record<string, string> = {}
  const pattern = /--([a-z0-9-]+)\s*:\s*([^;]+);/g
  for (const match of css.matchAll(pattern)) {
    const name = match[1]
    const value = match[2]?.trim()
    if (!name || !value) {
      continue
    }
    colors[name] = value
  }
  return colors
}

/**
 * Segue as referências `var(...)` de um token até chegar a uma cor
 * hexadecimal, no máximo 8 saltos. Um alias como `card-foreground` vira a
 * cor de `foreground`.
 *
 * @throws `ContrastError` com token ausente, com valor que não é cor nem
 *   referência e com referência em círculo.
 */
function resolveColor(name: string, colors: Readonly<Record<string, string>>) {
  let current = name
  for (let depth = 0; depth < 8; depth += 1) {
    const value = colors[current]
    if (!value) {
      throw new ContrastError(`Token ausente: ${current}`)
    }
    if (value.startsWith("#")) {
      return value
    }
    const reference = /^var\(--([a-z0-9-]+)\)$/.exec(value)
    if (!reference?.[1]) {
      throw new ContrastError(`Token ${current} não é uma cor: ${value}`)
    }
    current = reference[1]
  }
  throw new ContrastError(`Referência circular em ${name}`)
}

/**
 * Confere todos os pares e só lança no fim, com a lista das falhas: um
 * teste mostra todas de uma vez.
 *
 * @param minimum A razão mínima; 4,5 é o AA para texto pequeno.
 * @throws `ContrastError` se algum par ficar abaixo do mínimo.
 */
export function assertContrast(
  pairs: ReadonlyArray<readonly [string, string]>,
  colors: Readonly<Record<string, string>>,
  minimum = 4.5,
) {
  const failures: string[] = []
  for (const [foreground, background] of pairs) {
    const ratio = contrastRatio(
      resolveColor(foreground, colors),
      resolveColor(background, colors),
    )
    if (ratio < minimum) {
      failures.push(`${foreground} sobre ${background}: ${ratio.toFixed(2)}:1`)
    }
  }
  if (failures.length > 0) {
    throw new ContrastError(failures.join("\n"))
  }
}
