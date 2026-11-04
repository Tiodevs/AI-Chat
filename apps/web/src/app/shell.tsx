import { useQuery } from "@tanstack/react-query"
import { useEffect, useRef, useState } from "react"
import { useLocation, useOutlet } from "react-router"

import { viewerOf } from "@/app/navigation.ts"

import { focusPageTitle } from "@/app/page-heading.tsx"
import {
  AppSidebar,
  MobileSidebar,
} from "@/components/patterns/app-sidebar.tsx"
import { GuestHeader } from "@/components/patterns/guest-header.tsx"
import { SearchDialog } from "@/components/patterns/search-dialog.tsx"
import { meQuery } from "@/features/auth/useSession.ts"
import { useSignOut } from "@/features/auth/useSignOut.ts"
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
    { dependencies: [pathname, reduced], scope: rootRef }
  )

  return (
    <div key={pathname} ref={rootRef} className="flex flex-1 flex-col">
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
  const me = useQuery(meQuery)
  const viewer = viewerOf(me.data?.role)
  const guest = !me.isPending && viewer === "guest"
  const showSidebar = !me.isPending && !guest
  const signOut = useSignOut()
  const account = me.data
    ? {
        name: me.data.full_name.split(" ")[0] || me.data.full_name,
        onSignOut: () => {
          void signOut.signOut()
        },
        signingOut: signOut.pending,
        signOutError: signOut.error,
      }
    : undefined

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
      {showSidebar && !isMobile ? (
        <AppSidebar
          viewer={viewer}
          account={account}
          collapsed={collapsed}
          onSearch={() => {
            setSearchOpen(true)
          }}
          onToggleCollapsed={() => {
            setCollapsedChoice((current) => !(current ?? !isDesktop))
          }}
        />
      ) : null}
      <div className="flex min-w-0 flex-1 flex-col">
        {guest ? <GuestHeader compact={isMobile} /> : null}
        {showSidebar && isMobile ? (
          <MobileSidebar
            viewer={viewer}
            account={account}
            open={mobileOpen}
            onOpenChange={(open) => {
              setMenuPath(open ? pathname : null)
            }}
            onSearch={() => {
              setSearchOpen(true)
            }}
          />
        ) : null}
        <PageMain />
      </div>
      <SearchDialog
        open={searchOpen}
        onOpenChange={setSearchOpen}
        viewer={viewer}
      />
    </div>
  )
}

function PageMain() {
  return (
    <main
      id="conteudo"
      tabIndex={-1}
      className="min-h-0 min-w-0 flex-1 overflow-y-auto"
    >
      <div className="mx-auto flex min-h-full w-full max-w-7xl flex-col p-4 md:p-5 lg:p-6">
        <RouteTransition />
      </div>
    </main>
  )
}

export function Component() {
  return <AppShell />
}
