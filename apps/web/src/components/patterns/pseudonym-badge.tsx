/**
 * Identidade pseudonimizada de quem conversou: o tipo (Convidado ou
 * Membro) e o pseudônimo em fonte mono (seção 14.6).
 *
 * Aparece na tabela de conversas e no inspetor de `/admin/quality`
 * (seção 15.5). A seção 14.6 descreve o selo "com a ação de revelar"; no
 * código, Revelar identidade fica no inspetor, que pede o motivo antes de
 * chamar a API (seção 11.8). O selo só mostra o pseudônimo, nunca o nome.
 *
 * O ícone é `aria-hidden`; o tipo vai em texto.
 */
import { UserRound, UserRoundX } from "lucide-react"

/** Identidade pseudonimizada. A revelação fica no inspetor de qualidade. SDD 11.8 e 14.6. */
export function PseudonymBadge({
  kind,
  pseudonym,
  kindLabel,
}: {
  kind: "guest" | "member"
  /** Os 8 caracteres do HMAC que a API manda no lugar do nome (seção 12). */
  pseudonym: string
  /** Texto do tipo, de `pt.quality.subject`. */
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
