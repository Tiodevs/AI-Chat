/**
 * Selo do desfecho de uma resposta: Respondida, Não está nas informações
 * publicadas, Orientação médica recusada, Substituída e Indisponível
 * (seção 14.6).
 *
 * Usado pelo `AssistantMessage` para mostrar a incerteza sem fingir
 * certeza (seção 15.6). O tipo `answered` existe, mas a conversa não mostra
 * selo numa resposta normal.
 *
 * Cada tipo tem um tom (seção 14.1: cor só como status). O fundo é o par
 * translúcido da seção 14.2, com a cor a 15%, e o ponto é `aria-hidden`.
 * O texto diz o desfecho, então a cor nunca é o único sinal (seção 15.8).
 */
import { pt } from "@/i18n/pt.ts"
import { cn } from "@/lib/utils.ts"

// Tom de cada desfecho. `replaced` usa o mesmo `warning` da abstenção.
const kinds = {
  answered: "success",
  abstained: "warning",
  refused: "danger",
  replaced: "warning",
  unavailable: "info",
} as const

/** Os desfechos que têm selo. O texto vem de `pt.ask.outcomes`. */
export type OutcomeKind = keyof typeof kinds

// Classes completas no código, para o Tailwind achá-las na varredura.
const surfaces = {
  success: "bg-[color-mix(in_oklab,var(--success)_15%,transparent)]",
  warning: "bg-[color-mix(in_oklab,var(--warning)_15%,transparent)]",
  danger: "bg-[color-mix(in_oklab,var(--danger)_15%,transparent)]",
  info: "bg-[color-mix(in_oklab,var(--info)_15%,transparent)]",
} as const

const dots = {
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  info: "bg-info",
} as const

/** Pílula com ponto colorido e o texto do desfecho. */
export function OutcomeBadge({ kind }: { kind: OutcomeKind }) {
  const tone = kinds[kind]
  return (
    <span
      className={cn(
        "inline-flex w-fit items-center gap-2 rounded-full px-2.5 py-1 text-caption text-foreground",
        surfaces[tone]
      )}
    >
      <span
        aria-hidden="true"
        className={cn("size-2 rounded-full", dots[tone])}
      />
      {pt.ask.outcomes[kind]}
    </span>
  )
}
