/**
 * Card "Novidades" acima do rodapé da barra lateral, como o What's new da
 * imagem de referência, com uma dica de privacidade e de uso (seções 14.5
 * e 14.6).
 *
 * Aparece no `SidebarBody` com a barra expandida. Recolhida, o card some
 * e sai do foco e do leitor de tela. O texto vem de `pt.notice`.
 *
 * É o único uso do `Card` com o raio de 16 px (`rounded-card`) e a borda
 * `--border` (`ring-border`) da seção 14.4, sem sombra.
 */
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card.tsx"
import { pt } from "@/i18n/pt.ts"

/** Card fixo, sem props. */
export function SidebarNoticeCard() {
  return (
    <Card size="sm" className="rounded-card shadow-none ring-border">
      <CardHeader>
        <CardTitle className="text-label text-foreground">
          {pt.notice.title}
        </CardTitle>
        <CardDescription className="text-caption text-subtle-foreground">
          {pt.notice.body}
        </CardDescription>
      </CardHeader>
    </Card>
  )
}
