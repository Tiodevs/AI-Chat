import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group.tsx"
import { pt } from "@/i18n/pt.ts"

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
