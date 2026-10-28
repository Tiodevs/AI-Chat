import { pt } from "@/i18n/pt.ts"

export function CitationChip({
  index,
  onSelect,
}: {
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
