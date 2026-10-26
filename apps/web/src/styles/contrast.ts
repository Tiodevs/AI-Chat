const surfaces = [
  "shell",
  "background",
  "card",
  "popover",
  "muted",
] as const

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

export const textPairs: ReadonlyArray<readonly [string, string]> = [
  ...texts.flatMap((text) =>
    surfaces.map((surface) => [text, surface] as const),
  ),
  ["primary-foreground", "primary"],
]

export class ContrastError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "ContrastError"
  }
}

function channel(value: number) {
  const ratio = value / 255
  if (ratio <= 0.04045) {
    return ratio / 12.92
  }
  return ((ratio + 0.055) / 1.055) ** 2.4
}

function luminance(hex: string) {
  const value = Number.parseInt(hex.slice(1), 16)
  const red = channel((value >> 16) & 255)
  const green = channel((value >> 8) & 255)
  const blue = channel(value & 255)
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue
}

export function contrastRatio(foreground: string, background: string) {
  const first = luminance(foreground)
  const second = luminance(background)
  const lighter = Math.max(first, second)
  const darker = Math.min(first, second)
  return (lighter + 0.05) / (darker + 0.05)
}

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
