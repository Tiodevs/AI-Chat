/**
 * Barra lateral de quem tem sessão (seções 14.5 e 14.6): `AppSidebar` no
 * desktop e no tablet, e `MobileSidebar` no celular, com a barra de 56 px
 * no topo e o menu num sheet. O conteúdo das duas é o `SidebarBody`.
 *
 * Quem decide qual mostrar é a casca (`app/shell.tsx`), que carrega este
 * arquivo sob demanda: o visitante sem sessão não baixa a barra lateral,
 * o Flip nem o tooltip (seções 13.1 e 16.2).
 *
 * `AppSidebar` tem 240 px expandida e 64 px recolhida, só com ícones
 * (seção 14.5). Movimento M13 (seção 16.3): a largura troca direto, sem
 * animar `width`. No clique, o Flip registra a posição dos ícones; depois
 * que a classe muda, o preset `moveSidebar` leva cada ícone do lugar
 * antigo ao novo só com `transform`, e `showSidebarLabels` faz os rótulos
 * entrarem com `autoAlpha` ao expandir. Com movimento reduzido, tudo muda
 * direto.
 *
 * `MobileSidebar` usa M14: o sheet entra da esquerda com
 * `useGsapPresence` e `forceMount`. A saída nunca roda, porque o hook
 * desmonta o painel antes; a Etapa 14.3 do plano corrige o hook.
 */
import { Menu } from "lucide-react"
import { useRef } from "react"

import type { Viewer } from "@/app/navigation.ts"
import type { ProfileAccount } from "@/components/patterns/profile-button.tsx"
import { SidebarBody } from "@/components/patterns/sidebar-body.tsx"
import { Button } from "@/components/ui/button.tsx"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet.tsx"
import { pt } from "@/i18n/pt.ts"
import { Flip } from "@/motion/flip.ts"
import { useGSAP } from "@/motion/gsap.ts"
import { useMotion } from "@/motion/MotionProvider.tsx"
import { presets, type FlipState } from "@/motion/presets.ts"
import { useGsapPresence } from "@/motion/useGsapPresence.ts"
import { cn } from "@/lib/utils.ts"

/** Os ícones que existem com a barra recolhida e expandida (M13). */
const flipTargets = "[data-flip-id]"

/**
 * Barra lateral do desktop e do tablet, recolhível (M13).
 *
 * 1. No clique de recolher ou expandir, `toggleCollapsed` guarda o estado
 *    do Flip e só então pede a troca ao pai.
 * 2. Com o novo `collapsed`, o `useGSAP` anima os rótulos e os ícones a
 *    partir do estado guardado, e o descarta.
 */
export function AppSidebar({
  collapsed,
  onToggleCollapsed,
  onSearch,
  viewer = "admin",
  account,
}: {
  /** A casca começa recolhida abaixo de 1024 px e guarda a escolha. */
  collapsed: boolean
  onToggleCollapsed: () => void
  /** Abre a busca do `⌘K`. */
  onSearch: () => void
  /** Quem vê: escolhe os grupos da navegação. */
  viewer?: Viewer
  /** Nome e Sair para o `ProfileButton`; sem ele, o botão diz Visitante. */
  account?: ProfileAccount
}) {
  const rootRef = useRef<HTMLElement>(null)
  // A primeira execução é a montagem: nada a animar.
  const skipMotion = useRef(true)
  const flipState = useRef<FlipState | undefined>(undefined)
  const { reduced } = useMotion()

  // 2. Roda ao montar e a cada troca de `collapsed` ou do movimento.
  useGSAP(
    () => {
      const root = rootRef.current
      if (!root) {
        return
      }
      const labels = root.querySelectorAll("[data-sidebar-label]")
      const first = skipMotion.current
      skipMotion.current = false
      // Os presets recebem `reduced || first`: na montagem, eles se
      // comportam como no movimento reduzido e aplicam o estado direto.
      presets.showSidebarLabels(labels, reduced || first, !collapsed)
      presets.moveSidebar(
        root.querySelectorAll(flipTargets),
        reduced || first,
        flipState.current,
        Flip,
      )
      flipState.current = undefined
    },
    { dependencies: [collapsed, reduced], scope: rootRef },
  )

  // 1.
  // M13: o Flip registra os ícones antes de a classe mudar. Ao recolher, os links ganham o
  // tooltip e viram outros elementos, por isso o Flip os casa pelo `data-flip-id`.
  function toggleCollapsed() {
    const root = rootRef.current
    if (root) {
      flipState.current = Flip.getState(root.querySelectorAll(flipTargets), { simple: true })
    }
    onToggleCollapsed()
  }

  return (
    <aside
      // O botão de recolher aponta para este id em `aria-controls`.
      id="app-sidebar"
      ref={rootRef}
      data-collapsed={collapsed ? "true" : "false"}
      className={cn(
        "flex h-full shrink-0 flex-col overflow-hidden border-r border-border bg-shell py-3",
        collapsed ? "w-16 items-center" : "w-60 px-3",
      )}
    >
      <SidebarBody
        collapsed={collapsed}
        onSearch={onSearch}
        onToggle={toggleCollapsed}
        showCollapse
        viewer={viewer}
        account={account}
      />
    </aside>
  )
}

/**
 * Barra do topo do celular, com o botão de menu, e a barra lateral num
 * sheet à esquerda. Navegar, buscar ou sair fecha o sheet.
 */
export function MobileSidebar({
  open,
  onOpenChange,
  onSearch,
  viewer = "admin",
  account,
}: {
  /** A casca abre o menu por rota: trocar de página o fecha. */
  open: boolean
  onOpenChange: (open: boolean) => void
  onSearch: () => void
  viewer?: Viewer
  account?: ProfileAccount
}) {
  const panelRef = useRef<HTMLDivElement>(null)
  // M14: entra da esquerda, 24 px. `mounted` diz se o sheet existe.
  const mounted = useGsapPresence(open, panelRef, -24)

  return (
    <>
      {/* 56 px, a mesma altura do lugar que a casca reserva antes. */}
      <header className="flex h-14 items-center gap-3 border-b border-border bg-shell px-4">
        <Button
          variant="ghost"
          size="icon"
          className="size-11"
          aria-label={pt.sidebar.openMenu}
          aria-expanded={open}
          aria-controls="mobile-sidebar"
          onClick={() => {
            onOpenChange(true)
          }}
        >
          <Menu strokeWidth={1.75} />
        </Button>
        <span className="text-label text-foreground-strong">{pt.appName}</span>
      </header>
      <Sheet open={open} onOpenChange={onOpenChange}>
        {mounted ? (
          <SheetContent
            id="mobile-sidebar"
            ref={panelRef}
            // Mantém o painel montado enquanto o `useGsapPresence` quiser,
            // em vez de deixar o Radix desmontá-lo ao fechar.
            forceMount
            side="left"
            className="w-72 bg-shell p-3 data-[side=left]:w-72"
          >
            {/* Todo sheet tem título, mesmo escondido (seção 14.8). */}
            <SheetHeader className="sr-only">
              <SheetTitle>{pt.sidebar.label}</SheetTitle>
            </SheetHeader>
            <div className="min-h-0 flex-1">
              <SidebarBody
                collapsed={false}
                viewer={viewer}
                account={
                  account && {
                    ...account,
                    onSignOut: () => {
                      onOpenChange(false)
                      account.onSignOut()
                    },
                  }
                }
                onSearch={() => {
                  onOpenChange(false)
                  onSearch()
                }}
                onNavigate={() => {
                  onOpenChange(false)
                }}
              />
            </div>
          </SheetContent>
        ) : null}
      </Sheet>
    </>
  )
}
