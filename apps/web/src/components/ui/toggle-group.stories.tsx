import type { Meta, StoryObj } from "@storybook/react-vite"

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "UI/ToggleGroup",
  component: ToggleGroup,
} satisfies Meta<typeof ToggleGroup>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  args: { type: "single" },
  render: () => (
    <div className="flex flex-col gap-6">
      <ToggleGroup
        type="single"
        aria-label={pt.ask.suggestionsLabel}
        defaultValue="visiting"
      >
        {pt.ask.suggestions.map((suggestion) => (
          <ToggleGroupItem key={suggestion.id} value={suggestion.id}>
            {suggestion.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
      <ToggleGroup type="single" aria-label={pt.ask.suggestionsLabel}>
        <ToggleGroupItem value="focus" autoFocus>
          {pt.ask.suggestions[1].label}
        </ToggleGroupItem>
      </ToggleGroup>
      <ToggleGroup type="single" aria-label={pt.ask.suggestionsLabel} disabled>
        <ToggleGroupItem value="disabled">
          {pt.ask.suggestions[2].label}
        </ToggleGroupItem>
      </ToggleGroup>
      <ToggleGroup type="single" aria-label={pt.ask.suggestionsLabel}>
        <ToggleGroupItem
          value="invalid"
          aria-invalid="true"
          aria-describedby="chip-error"
        >
          {pt.ask.suggestions[3].label}
        </ToggleGroupItem>
      </ToggleGroup>
      <p id="chip-error" className="text-caption text-danger">
        {pt.couldNotContinue}
      </p>
    </div>
  ),
}
