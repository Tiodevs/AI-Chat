/**
 * Conteúdo da barra lateral, igual no desktop e no celular (seções 14.5,
 * 14.6 e 15.4): logotipo e botão de recolher no topo, busca com o atalho,
 * os grupos de navegação, o `SidebarNoticeCard` e o `ProfileButton` no
 * rodapé.
 *
 * Usado só pelo `AppSidebar` e pelo `MobileSidebar`; não tem história
 * própria, e as histórias do `AppSidebar` o mostram. Os grupos vêm de
 * `navigationFor(viewer)`, em `app/navigation.ts`: Assistente e Conta
 * para o membro, mais Operação e Sistema para o admin.
 *
 * Estados de interação (seção 14.7): item inativo em `--muted-foreground`,
 * que no hover ganha o fundo `--muted` e o texto `--foreground`; item
 * ativo em `--card`. Itens de 44 px no celular e 32 px no desktop (seção
 * 15.8), com o raio de navegação de 10 px (`rounded-nav`, seção 14.4).
 *
 * Recolhida (M13): os rótulos ficam em `sr-only`, nunca com
 * `visibility: hidden`, e continuam dando nome aos links (WCAG 2.5.3,
 * seção 15.8); cada link ganha um tooltip à direita. Os ícones levam
 * `data-flip-id`, que o Flip usa para achar o mesmo ícone antes e depois.
 */
import { PanelLeftClose, PanelLeftOpen, Search } from "lucide-react"
import { NavLink } from "react-router"

import {
  ProfileButton,
  type ProfileAccount,
} from "@/components/patterns/profile-button.tsx"
import { SidebarNoticeCard } from "@/components/patterns/sidebar-notice-card.tsx"
import { Button } from "@/components/ui/button.tsx"
import { Separator } from "@/components/ui/separator.tsx"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip.tsx"
import { navigationFor, type NavItem, type Viewer } from "@/app/navigation.ts"
import { pt } from "@/i18n/pt.ts"
import { cn } from "@/lib/utils.ts"

// O atalho que a busca mostra: `⌘K` nos aparelhos da Apple e `Ctrl+K`
// nos outros (seção 15.8). Sem `navigator`, fica o `⌘K`.
function commandShortcutLabel() {
  if (typeof navigator === "undefined") {
    return "⌘K"
  }
  return /Mac|iPhone|iPad/.test(navigator.userAgent) ? "⌘K" : "Ctrl+K"
}

// Classes de um item da navegação. Recolhida, o item é um quadrado de
// 32 px só com o ícone; a barra recolhida não existe no celular.
function itemClass(collapsed: boolean, active = false) {
  return cn(
    "flex items-center rounded-nav text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground",
    collapsed
      ? "size-8 justify-center"
      : "h-11 md:h-8 w-full min-w-0 gap-2 px-2.5",
    active && "bg-card text-foreground hover:bg-card hover:text-foreground",
  )
}

/**
 * Um link da navegação. O `NavLink` do React Router marca a rota atual
 * com `aria-current="page"` e passa `isActive` para a classe. Recolhida,
 * o link vai dentro de um `Tooltip`.
 */
function SidebarLink({
  item,
  collapsed,
  onNavigate,
}: {
  item: NavItem
  collapsed: boolean
  onNavigate?: () => void
}) {
  const Icon = item.icon
  const link = (
    <NavLink
      to={item.to}
      // `end` ativa o link só na rota exata. Conversas (`/ask`) não o
      // usa e fica ativo também em `/ask/:id`.
      end={item.end ?? false}
      aria-label={item.label}
      onClick={onNavigate}
      className={({ isActive }) => itemClass(collapsed, isActive)}
    >
      <Icon
        className="size-4 shrink-0"
        strokeWidth={1.75}
        aria-hidden="true"
        data-flip-id={`nav:${item.to}`}
      />
      <span data-sidebar-label className={cn("truncate", collapsed && "sr-only")}>
        {item.label}
      </span>
    </NavLink>
  )

  if (!collapsed) {
    return link
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>{link}</TooltipTrigger>
      <TooltipContent side="right">{item.label}</TooltipContent>
    </Tooltip>
  )
}

/** O conteúdo da barra, de cima para baixo. */
function SidebarContent({
  collapsed,
  onSearch,
  onNavigate,
  onToggle,
  showCollapse = false,
  viewer = "admin",
  account,
}: {
  collapsed: boolean
  onSearch: () => void
  /** Chamado ao escolher um link; o celular fecha o sheet. */
  onNavigate?: () => void
  onToggle?: () => void
  /** Mostra o botão de recolher, só no `AppSidebar`. */
  showCollapse?: boolean
  viewer?: Viewer
  account?: ProfileAccount
}) {
  return (
    <div
      className={cn(
        "flex h-full min-h-0 w-full flex-col",
        collapsed ? "items-center gap-5" : "gap-3",
      )}
    >
      <div
        className={cn(
          "flex items-center",
          collapsed ? "w-8 flex-col gap-5" : "gap-2",
        )}
      >
        <NavLink
          to="/"
          end
          onClick={onNavigate}
          className={cn(
            "flex min-w-0 items-center rounded-nav text-sm font-medium text-foreground-strong",
            collapsed ? "size-8 justify-center" : "h-11 md:h-8 flex-1 gap-2 px-2.5",
          )}
        >
          <span
            aria-hidden="true"
            data-flip-id="logo"
            className="flex size-4 shrink-0 items-center justify-center rounded-md bg-primary text-[10px] leading-none font-medium text-primary-foreground"
          >
            A
          </span>
          <span data-sidebar-label className={cn("truncate", collapsed && "sr-only")}>
            {pt.appName}
          </span>
        </NavLink>
        {/* Recolher: `aria-expanded` diz se a barra está aberta, e o nome */}
        {/* troca entre "Recolher barra lateral" e "Expandir barra lateral". */}
        {showCollapse && onToggle ? (
          <Button
            variant="ghost"
            size="icon"
            className="size-8 shrink-0"
            aria-expanded={!collapsed}
            aria-controls="app-sidebar"
            aria-label={collapsed ? pt.sidebar.expand : pt.sidebar.collapse}
            onClick={onToggle}
          >
            {collapsed ? (
              <PanelLeftOpen className="size-4" strokeWidth={1.75} data-flip-id="collapse" />
            ) : (
              <PanelLeftClose className="size-4" strokeWidth={1.75} data-flip-id="collapse" />
            )}
          </Button>
        ) : null}
      </div>

      {/* A busca: `aria-keyshortcuts` diz ao leitor de tela que o */}
      {/* atalho existe; quem o escuta é a casca (`app/shell.tsx`). */}
      <Button
        variant="outline"
        aria-keyshortcuts="Meta+K Control+K"
        onClick={onSearch}
        className={cn(
          collapsed
            ? "grid size-8 place-items-center p-0 px-0"
            : "h-11 md:h-8 w-full justify-start px-2.5",
        )}
      >
        <Search
          className="size-4"
          strokeWidth={1.75}
          data-icon={collapsed ? undefined : "inline-start"}
          data-flip-id="search"
        />
        <span
          data-sidebar-label
          className={cn(
            "flex min-w-0 flex-1 items-center justify-between gap-2",
            collapsed && "sr-only",
          )}
        >
          <span className="truncate">{pt.sidebar.search}</span>
          <kbd className="font-mono text-caption text-subtle-foreground">
            {commandShortcutLabel()}
          </kbd>
        </span>
      </Button>

      <nav
        aria-label={pt.sidebar.label}
        data-sidebar-nav
        className={cn(
          "flex min-h-0 w-full flex-1 flex-col overflow-x-hidden overflow-y-auto",
          collapsed ? "scrollbar-none items-center gap-5" : "gap-5",
        )}
      >
        {navigationFor(viewer).map((group) => (
          <div
            key={group.label}
            className={cn(
              "flex flex-col",
              collapsed ? "items-center gap-5" : "gap-1",
            )}
          >
            <p
              data-sidebar-label
              className={cn(
                "px-2.5 text-label text-subtle-foreground",
                collapsed && "sr-only",
              )}
            >
              {group.label}
            </p>
            <ul className={cn("flex flex-col", collapsed ? "items-center gap-5" : "gap-1")}>
              {group.items.map((item) => (
                <li key={item.to}>
                  <SidebarLink
                    item={item}
                    collapsed={collapsed}
                    onNavigate={onNavigate}
                  />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      <Separator className={collapsed ? "w-8" : "w-full"} />

      <div className={cn("flex w-full flex-col", collapsed ? "items-center" : "gap-3")}>
        {/* A linha da grade vai de `1fr` a `0fr` e some com o card sem */}
        {/* animar altura. Recolhido, `inert` e `aria-hidden` tiram o card */}
        {/* do foco e do leitor de tela. */}
        <div className={cn("grid w-full", collapsed ? "grid-rows-[0fr]" : "grid-rows-[1fr]")}>
          <div
            className="min-h-0 overflow-hidden"
            inert={collapsed ? true : undefined}
            aria-hidden={collapsed}
          >
            <SidebarNoticeCard />
          </div>
        </div>
        <ProfileButton collapsed={collapsed} {...account} />
      </div>
    </div>
  )
}

type SidebarBodyProps = Parameters<typeof SidebarContent>[0]

/** O provider vive aqui, e não na raiz: o visitante sem sessão não baixa o tooltip. */
export function SidebarBody(props: SidebarBodyProps) {
  return (
    <TooltipProvider>
      <SidebarContent {...props} />
    </TooltipProvider>
  )
}
