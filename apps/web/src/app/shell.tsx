import { useEffect, useRef, useState } from "react"
import { useLocation, useOutlet } from "react-router"

import { focusPageTitle } from "@/app/page-heading.tsx"
import { AppSidebar, MobileSidebar } from "@/components/patterns/app-sidebar.tsx"
import { SearchDialog } from "@/components/patterns/search-dialog.tsx"
import { pt } from "@/i18n/pt.ts"
import { useGSAP } from "@/motion/gsap.ts"
import { useMotion } from "@/motion/MotionProvider.tsx"
import { presets } from "@/motion/presets.ts"

function RouteTransition() {
  const outlet = useOutlet()
  const { pathname } = useLocation()
  const rootRef = useRef<HTMLDivElement>(null)
  const skipFocus = useRef(true)
  const skipFocusEffect = useRef(true)
  const { reduced } = useMotion()

  useEffect(() => {
    if (skipFocusEffect.current) {
      skipFocusEffect.current = false
      return
    }
    focusPageTitle()
  }, [pathname])

  useGSAP(
    () => {
      const root = rootRef.current
      if (!root) {
        return
      }
      const cards = root.querySelectorAll("[data-motion-card]")
      const target = cards.length > 0 ? cards : root
      const skip = skipFocus.current
      skipFocus.current = false
      presets.enterRoute(target, reduced || skip, () => {
        if (!skip) {
          focusPageTitle()
        }
      })
    },
    { dependencies: [pathname, reduced], scope: rootRef },
  )

  return (
    <div key={pathname} ref={rootRef}>
      {outlet}
    </div>
  )
}

export function AppShell() {
  const { isDesktop, isMobile } = useMotion()
  const [collapsedChoice, setCollapsedChoice] = useState<boolean | null>(null)
  const collapsed = collapsedChoice ?? !isDesktop
  const [searchOpen, setSearchOpen] = useState(false)
  const [menuPath, setMenuPath] = useState<string | null>(null)
  const { pathname } = useLocation()
  const mobileOpen = menuPath === pathname

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() !== "k" || event.repeat) {
        return
      }
      if (!event.metaKey && !event.ctrlKey) {
        return
      }
      event.preventDefault()
      setSearchOpen(true)
    }
    window.addEventListener("keydown", onKeyDown)
    return () => {
      window.removeEventListener("keydown", onKeyDown)
    }
  }, [])

  return (
    <div className="flex h-dvh overflow-hidden bg-background text-foreground">
      <a
        href="#conteudo"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
      >
        {pt.skipToContent}
      </a>
      {isMobile ? (
        <div className="flex min-w-0 flex-1 flex-col">
          <MobileSidebar
            open={mobileOpen}
            onOpenChange={(open) => {
              setMenuPath(open ? pathname : null)
            }}
            onSearch={() => {
              setSearchOpen(true)
            }}
          />
          <PageMain />
        </div>
      ) : (
        <>
          <AppSidebar
            collapsed={collapsed}
            onSearch={() => {
              setSearchOpen(true)
            }}
            onToggleCollapsed={() => {
              setCollapsedChoice((current) => !(current ?? !isDesktop))
            }}
          />
          <PageMain />
        </>
      )}
      <SearchDialog open={searchOpen} onOpenChange={setSearchOpen} />
    </div>
  )
}

function PageMain() {
  return (
    <main
      id="conteudo"
      tabIndex={-1}
      className="min-w-0 flex-1 overflow-y-auto p-4 md:p-5 lg:p-6"
    >
      <div className="mx-auto flex w-full max-w-7xl flex-col">
        <RouteTransition />
      </div>
    </main>
  )
}

export function Component() {
  return <AppShell />
}
