/**
 * Aviso permanente de que o Atrium é uma IA e não dá orientação médica
 * (seções 14.6 e 15.6, declarar que é IA).
 *
 * Aparece na página inicial (`/`), abaixo das sugestões (seção 15.5). O
 * texto vem de `pt.safety`.
 *
 * A seção 14.6 descreve um `Alert` do shadcn; o projeto não tem esse
 * componente, e o aviso é um `aside` com título `h2`, em `--card` com a
 * borda `--border`. Sem `role="alert"`: o aviso é fixo, não uma mudança
 * que precise ser anunciada.
 */
import { pt } from "@/i18n/pt.ts"

/** Caixa do aviso, sem props: o texto é sempre o mesmo. */
export function SafetyNotice() {
  return (
    <aside className="flex flex-col gap-2 rounded-2xl border border-border bg-card px-4 py-4 md:px-5">
      <h2 className="text-label text-foreground">{pt.safety.title}</h2>
      <p className="text-body text-foreground">{pt.safety.body}</p>
    </aside>
  )
}
