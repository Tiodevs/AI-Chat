/**
 * Marcador numerado de citação dentro do texto da resposta (seção 14.6).
 *
 * O `AssistantMessage` troca cada `[n]` do texto por um chip; o clique
 * abre o `SourceList` e põe o foco na fonte `n`. Toda resposta de fato
 * mostra de onde vem (seções 15.1 e 15.6).
 *
 * Acessibilidade: é um `button` com o nome "Fontes n", que contém o
 * número visível (WCAG 2.5.3). Tem 24 px: dentro de uma frase, vale a
 * exceção do WCAG 2.5.8 para alvos no texto (seção 15.8). Sem
 * `outline-none`, mostra o contorno de foco global.
 *
 * Movimento: M8 (seção 16.3). O `data-citation` é o gancho que o
 * `AssistantMessage` usa para animar os chips com `enterCitations`.
 */
import { pt } from "@/i18n/pt.ts"

/** Um chip de citação, com o número da fonte. */
export function CitationChip({
  index,
  onSelect,
}: {
  /** Número da citação, o mesmo do marcador `[n]` e da lista de fontes. */
  index: number
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      data-citation
      onClick={onSelect}
      className="mx-0.5 inline-flex min-h-6 min-w-6 items-center justify-center rounded-full bg-muted px-1.5 align-middle text-caption text-foreground hover:bg-border-strong"
      aria-label={`${pt.ask.sources} ${index}`}
    >
      {index}
    </button>
  )
}
