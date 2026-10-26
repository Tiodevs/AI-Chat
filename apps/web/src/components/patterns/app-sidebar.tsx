import { Menu } from "lucide-react"
import { useRef } from "react"

import { SidebarBody } from "@/components/patterns/sidebar-body.tsx"
import { Button } from "@/components/ui/button.tsx"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet.tsx"
import { pt } from "@/i18n/pt.ts"
import { useGSAP } from "@/motion/gsap.ts"
import { useMotion } from "@/motion/MotionProvider.tsx"
import { presets } from "@/motion/presets.ts"
import { useGsapPresence } from "@/motion/useGsapPresence.ts"
import { cn } from "@/lib/utils.ts"

export function AppSidebar({
  collapsed,
  onToggleCollapsed,
  onSearch,
}: {
  collapsed: boolean
  onToggleCollapsed: () => void
  onSearch: () => void
}) {
  const rootRef = useRef<HTMLElement>(null)
  const skipMotion = useRef(true)
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
    },
    { dependencies: [collapsed, reduced], scope: rootRef },
  )

  return (
    <aside
      id="app-sidebar"
      ref={rootRef}
      data-collapsed={collapsed ? "true" : "false"}
      className={cn(
        "flex h-full shrink-0 flex-col overflow-hidden border-r border-border bg-shell py-3",
        collapsed ? "w-16 items-center" : "w-60 px-3",
        !reduced && "transition-[width] duration-300 ease-in-out",
      )}
    >
      <SidebarBody
        collapsed={collapsed}
        onSearch={onSearch}
        onToggle={onToggleCollapsed}
        showCollapse
      />
    </aside>
  )
}

export function MobileSidebar({
  open,
  onOpenChange,
  onSearch,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSearch: () => void
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
