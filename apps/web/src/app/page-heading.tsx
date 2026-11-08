/**
 * O título de cada página e o foco nele na troca de rota (seção 15.8).
 *
 * Quem usa: as telas de `features`, a rota `routes/sign-in.tsx` e o
 * `ErrorBoundary` de `route-frame.tsx` (`PageHeading`); a casca,
 * `shell.tsx` (`focusPageTitle`).
 */
import { useEffect } from "react"

import { pt } from "@/i18n/pt.ts"

/**
 * O `h1` da página, com o id `page-title`, e o título da aba.
 *
 * Efeito colateral: grava `document.title` como "título · Atrium" sempre
 * que o título muda. `tabIndex={-1}` deixa o `h1` receber foco por código
 * sem entrar na ordem do Tab. O id é fixo, porque o foco e o
 * `aria-labelledby` de algumas telas acham o título por ele: cada página
 * tem um `PageHeading` só.
 *
 * @param variant `display` para o título grande do início, `title` para as
 *   outras páginas (tipografia da seção 14.3).
 */
export function PageHeading({
  title,
  variant = "title",
}: {
  title: string
  variant?: "title" | "display"
}) {
  useEffect(() => {
    document.title = `${title} · ${pt.appName}`
  }, [title])

  return (
    <h1
      id="page-title"
      tabIndex={-1}
      className={
        variant === "display"
          ? "text-display text-foreground-strong"
          : "text-title text-foreground-strong"
      }
    >
      {title}
    </h1>
  )
}

/**
 * Põe o foco no título da página atual, sem rolar até ele. Sem título na
 * tela, não faz nada. A casca chama esta função na troca de rota: o foco
 * sai do link clicado e vai para o começo da página nova (seção 15.8).
 */
export function focusPageTitle() {
  const heading = document.getElementById("page-title")
  if (!(heading instanceof HTMLElement)) {
    return
  }
  heading.focus({ preventScroll: true })
}
