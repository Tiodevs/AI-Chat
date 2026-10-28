import { pt } from "@/i18n/pt.ts"

export function SafetyNotice() {
  return (
    <aside className="flex flex-col gap-2 rounded-2xl border border-border bg-card px-4 py-4 md:px-5">
      <h2 className="text-label text-foreground">{pt.safety.title}</h2>
      <p className="text-body text-foreground">{pt.safety.body}</p>
    </aside>
  )
}
