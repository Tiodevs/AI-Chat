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
import { Flip, useGSAP } from "@/motion/gsap.ts"
import { useMotion } from "@/motion/MotionProvider.tsx"
import { presets, type FlipState } from "@/motion/presets.ts"
import { useGsapPresence } from "@/motion/useGsapPresence.ts"
import { cn } from "@/lib/utils.ts"

/** Os ícones que existem com a barra recolhida e expandida (M13). */
const flipTargets = "[data-flip-id]"

export function AppSidebar({
  collapsed,
  onToggleCollapsed,
  onSearch,
  viewer = "admin",
  account,
}: {
  collapsed: boolean
  onToggleCollapsed: () => void
  onSearch: () => void
  viewer?: Viewer
  account?: ProfileAccount
}) {
  const rootRef = useRef<HTMLElement>(null)
  const skipMotion = useRef(true)
  const flipState = useRef<FlipState | undefined>(undefined)
  const { reduced } = useMotion()

  useGSAP(
    () => {
      const root = rootRef.current
      if (!root) {
        return
      }
      const labels = root.querySelectorAll("[data-sidebar-label]")
      const first = skipMotion.current
      skipMotion.current = false
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

export function MobileSidebar({
  open,
  onOpenChange,
  onSearch,
  viewer = "admin",
  account,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSearch: () => void
  viewer?: Viewer
  account?: ProfileAccount
}) {
  const panelRef = useRef<HTMLDivElement>(null)
  const mounted = useGsapPresence(open, panelRef, -24)

  return (
    <>
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
            forceMount
            side="left"
            className="w-72 bg-shell p-3 data-[side=left]:w-72"
          >
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
