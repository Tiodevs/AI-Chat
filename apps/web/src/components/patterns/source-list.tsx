/**
 * Lista recolhível das fontes de uma resposta, com título e seção de cada
 * documento (seções 14.6 e 15.5).
 *
 * Aparece no fim do `AssistantMessage` concluído. O estado aberto fica no
 * pai, porque o `CitationChip` também abre a lista. Sem citações, não
 * renderiza nada.
 *
 * Acessibilidade: o botão Mostrar fontes é um disclosure com
 * `aria-expanded`. Cada fonte tem `id="source-<chunkId>"` e
 * `tabIndex={-1}`: o chip pode pôr o foco nela por código, sem que ela
 * entre na ordem de tabulação. Alvo de 44 px no celular (seção 15.8).
 */
import type { CitationView } from "@/features/ask/types.ts"
import { Button } from "@/components/ui/button.tsx"
import { pt } from "@/i18n/pt.ts"

/** Botão de mostrar e ocultar e a lista numerada das fontes. */
export function SourceList({
  citations,
  open,
  onOpenChange,
}: {
  citations: CitationView[]
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  if (citations.length === 0) {
    return null
  }
  return (
    <div className="flex flex-col gap-2">
      <Button
        type="button"
        variant="outline"
        className="min-h-11 w-fit md:min-h-8"
        aria-expanded={open}
        onClick={() => {
          onOpenChange(!open)
        }}
      >
        {open ? pt.ask.hideSources : pt.ask.showSources}
      </Button>
      {open ? (
        <ol className="m-0 flex list-none flex-col gap-2 p-0">
          {citations.map((citation) => (
            <li
              key={citation.chunkId}
              id={`source-${citation.chunkId}`}
              tabIndex={-1}
              className="flex flex-col gap-1 rounded-2xl border border-border bg-card px-4 py-3"
            >
              <span className="text-body text-foreground">
                {citation.index}. {citation.documentTitle}
              </span>
              {citation.heading ? (
                <span className="text-caption text-subtle-foreground">
                  {citation.heading}
                </span>
              ) : null}
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  )
}
