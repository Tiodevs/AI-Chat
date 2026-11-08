/**
 * Cabeçalho do visitante sem sessão, no lugar da barra lateral (seções
 * 14.5 e 14.6): logotipo e as ações Entrar, Criar conta e Cadastrar com
 * IA, de `guestActions` em `app/navigation.ts`.
 *
 * A casca (`app/shell.tsx`) o mostra em todas as telas sem sessão, com
 * `compact` no celular. Largo, as ações são botões numa `nav`. No
 * celular, elas ficam no `GuestMenu`, um disclosure de navegação.
 *
 * Tem 56 px de altura, a mesma da barra que a casca reserva enquanto a
 * sessão não chega, para o conteúdo não pular.
 */
import { Menu } from "lucide-react"
import { useEffect, useId, useRef, useState } from "react"
import { Link, NavLink } from "react-router"

import { guestActions } from "@/app/navigation.ts"
import { Button } from "@/components/ui/button.tsx"
import { pt } from "@/i18n/pt.ts"
import { useGsapPresence } from "@/motion/useGsapPresence.ts"

/**
 * Menu do visitante no celular: um disclosure de navegação (botão com `aria-expanded` e uma
 * lista de links), o padrão do WAI-ARIA para navegação de site. Fecha com Esc, com um toque
 * fora e ao escolher um link. Sem o Radix Menu, a página inicial do visitante não baixa o
 * posicionamento flutuante (seção 5.3). A entrada e a saída seguem M14.
 */
function GuestMenu() {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLElement>(null)
  const panelId = useId()
  // M14 sem Radix. A saída não roda: o hook desmonta o painel antes
  // (achado da Etapa 14.3).
  const mounted = useGsapPresence(open, panelRef)

  // Só com o menu aberto: Esc fecha e devolve o foco ao botão, e um toque
  // fora do componente fecha sem mexer no foco.
  useEffect(() => {
    if (!open) {
      return
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false)
        buttonRef.current?.focus()
      }
    }
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("keydown", onKeyDown)
    document.addEventListener("pointerdown", onPointerDown)
    return () => {
      document.removeEventListener("keydown", onKeyDown)
      document.removeEventListener("pointerdown", onPointerDown)
    }
  }, [open])

  return (
    <div ref={rootRef} className="relative">
      <Button
        ref={buttonRef}
        variant="outline"
        className="min-h-11"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => {
          setOpen((current) => !current)
        }}
      >
        <Menu strokeWidth={1.75} data-icon="inline-start" aria-hidden="true" />
        {pt.sidebar.guestMenu}
      </Button>
      {mounted ? (
        <nav
          id={panelId}
          ref={panelRef}
          aria-label={pt.sidebar.guestMenu}
          className="absolute top-full right-0 z-50 mt-2 min-w-56 rounded-xl bg-popover p-1 shadow-overlay ring-1 ring-border"
        >
          <ul className="m-0 flex list-none flex-col p-0">
            {guestActions.map((action) => {
              const Icon = action.icon
              return (
                <li key={action.to}>
                  {/* Links de 44 px (seção 15.8); escolher um fecha o menu. */}
                  <Link
                    to={action.to}
                    className="flex min-h-11 items-center gap-2 rounded-lg px-3 text-body text-foreground hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                    onClick={() => {
                      setOpen(false)
                    }}
                  >
                    <Icon className="size-4" strokeWidth={1.75} aria-hidden="true" />
                    {action.label}
                  </Link>
                </li>
              )
            })}
          </ul>
        </nav>
      ) : null}
    </div>
  )
}

/** Cabeçalho de quem ainda não entrou: sem barra lateral, só entrar e criar conta. SDD 14.5. */
export function GuestHeader({ compact }: { compact: boolean }) {
  // `compact` vem do `isMobile` do `MotionProvider` (abaixo de 768 px).
  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-border bg-shell px-4 md:px-6">
      <Link
        to="/"
        className="flex min-h-11 items-center gap-2 rounded-nav text-sm font-medium text-foreground-strong md:min-h-8"
      >
        <span
          aria-hidden="true"
          className="flex size-6 shrink-0 items-center justify-center rounded-md bg-primary text-caption font-medium text-primary-foreground"
        >
          A
        </span>
        {pt.appName}
      </Link>
      {compact ? (
        <GuestMenu />
      ) : (
        <nav aria-label={pt.sidebar.guestMenu}>
          <ul className="m-0 flex list-none items-center gap-2 p-0">
            {guestActions.map((action) => {
              const Icon = action.icon
              return (
                <li key={action.to}>
                  {/* `asChild`: o `NavLink` recebe o estilo do botão. Na */}
                  {/* página da própria ação, ganha um anel de `--ring`. */}
                  <Button asChild variant={action.variant} className="h-8">
                    <NavLink
                      to={action.to}
                      end
                      className={({ isActive }) =>
                        isActive ? "ring-1 ring-ring" : undefined
                      }
                    >
                      <Icon strokeWidth={1.75} data-icon="inline-start" aria-hidden="true" />
                      {action.label}
                    </NavLink>
                  </Button>
                </li>
              )
            })}
          </ul>
        </nav>
      )}
    </header>
  )
}
