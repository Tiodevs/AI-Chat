import { UserRound, UserRoundX } from "lucide-react"

/** Identidade pseudonimizada. A revelação fica no inspetor de qualidade. SDD 11.8 e 14.6. */
export function PseudonymBadge({
  kind,
  pseudonym,
  kindLabel,
}: {
  kind: "guest" | "member"
  pseudonym: string
  kindLabel: string
}) {
  const Icon = kind === "guest" ? UserRoundX : UserRound
  return (
    <span className="inline-flex w-fit items-center gap-2 rounded-full bg-muted px-2.5 py-1 text-caption text-foreground">
      <Icon className="size-3.5 text-muted-foreground" strokeWidth={1.75} aria-hidden="true" />
      <span>{kindLabel}</span>
      <span className="font-mono text-muted-foreground">{pseudonym}</span>
    </span>
  )
}
