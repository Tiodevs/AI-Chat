/**
 * As quatro sugestões prontas da seção 15.5 do SDD: Horário de visita,
 * Estacionamento, Entrada de emergência e Horário do refeitório.
 *
 * View usada por `home-screen.tsx` e, na conversa vazia, por
 * `conversation-screen.tsx`. Os rótulos e as perguntas vêm de
 * `pt.ask.suggestions`.
 */
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group.tsx"
import { pt } from "@/i18n/pt.ts"

/**
 * Chips num `ToggleGroup` do shadcn/ui, sobre o Radix, com seleção única.
 * Escolher um chip envia a pergunta dele por `onSelect`.
 */
export function SuggestionChips({
  disabled,
  onSelect,
}: {
  disabled: boolean
  onSelect: (question: string) => void
}) {
  return (
    <ToggleGroup
      type="single"
      aria-label={pt.ask.suggestionsLabel}
      className="flex flex-wrap gap-2"
      onValueChange={(value) => {
        // O Radix entrega o `value` do item escolhido. Clicar de novo no
        // mesmo chip o desmarca e entrega vazio, que não acha sugestão.
        const suggestion = pt.ask.suggestions.find((item) => item.id === value)
        if (suggestion) {
          onSelect(suggestion.question)
        }
      }}
    >
      {pt.ask.suggestions.map((suggestion) => (
        <ToggleGroupItem
          key={suggestion.id}
          value={suggestion.id}
          disabled={disabled}
        >
          {suggestion.label}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  )
}
