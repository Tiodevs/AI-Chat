import { useQuery } from "@tanstack/react-query"
import { lazy, Suspense, useEffect, useRef, useState } from "react"
import { useLocation, useOutlet } from "react-router"

import { viewerOf } from "@/app/navigation.ts"

import { focusPageTitle } from "@/app/page-heading.tsx"
import { GuestHeader } from "@/components/patterns/guest-header.tsx"
import { meQuery } from "@/features/auth/useSession.ts"
import { useSignOut } from "@/features/auth/useSignOut.ts"
import { pt } from "@/i18n/pt.ts"
import { useGSAP } from "@/motion/gsap.ts"
import { useMotion } from "@/motion/MotionProvider.tsx"
import { presets } from "@/motion/presets.ts"
import { cn } from "@/lib/utils.ts"

// O visitante sem sessão, a pessoa que mais usa a página inicial, não baixa a barra lateral
// nem a paleta de comandos no primeiro carregamento (seção 5.3, JavaScript inicial de /).
const loadSidebar = () => import("@/components/patterns/app-sidebar.tsx")
const AppSidebar = lazy(() => loadSidebar().then((module) => ({ default: module.AppSidebar })))
const MobileSidebar = lazy(() =>
  loadSidebar().then((module) => ({ default: module.MobileSidebar })),
)
const loadSearch = () => import("@/components/patterns/search-dialog.tsx")
const SearchDialog = lazy(() => loadSearch().then((module) => ({ default: module.SearchDialog })))

/** Reserva o espaço da barra lateral enquanto ela carrega, sem deslocar o conteúdo. */
function SidebarPlaceholder({ collapsed }: { collapsed: boolean }) {
  return (
    <div
      aria-hidden="true"
      className={cn("h-full shrink-0 border-r border-border bg-shell", collapsed ? "w-16" : "w-60")}
    />
  )
}

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
        if (skip) {
          return
        }
        // Durante a entrada (M1) o conteúdo fica invisível e o título não recebe foco; ele o
        // recebe no fim. Se nesse meio-tempo a pessoa já entrou na página nova, clicando ou
        // digitando num campo, o foco fica onde ela o pôs (SDD 15.8).
        const active = document.activeElement
        if (active && active !== document.body && root.contains(active)) {
          return
        }
        focusPageTitle()
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
  const [searchMounted, setSearchMounted] = useState(false)
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

  function openSearch() {
    setSearchMounted(true)
    setSearchOpen(true)
  }

  // A paleta chega quando o navegador fica livre, para o ⌘K abrir sem espera.
  useEffect(() => {
    const prefetch = () => {
      void loadSearch()
    }
    if (typeof window.requestIdleCallback === "function") {
      const handle = window.requestIdleCallback(prefetch, { timeout: 4000 })
      return () => {
        window.cancelIdleCallback(handle)
      }
    }
    const timer = window.setTimeout(prefetch, 2000)
    return () => {
      window.clearTimeout(timer)
    }
  }, [])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() !== "k" || event.repeat) {
        return
      }
      if (!event.metaKey && !event.ctrlKey) {
        return
      }
      event.preventDefault()
      setSearchMounted(true)
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
        <Suspense fallback={<SidebarPlaceholder collapsed={collapsed} />}>
          <AppSidebar
            viewer={viewer}
            account={account}
            collapsed={collapsed}
            onSearch={openSearch}
            onToggleCollapsed={() => {
              setCollapsedChoice((current) => !(current ?? !isDesktop))
            }}
          />
        </Suspense>
      ) : null}
      <div className="flex min-w-0 flex-1 flex-col">
        {me.isPending && isMobile ? (
          // No celular, o visitante e o membro têm a mesma barra de 56 px no topo. Ela ocupa o
          // lugar enquanto a sessão não chega, e o conteúdo não pula (CLS, seção 5.3).
          <div aria-hidden="true" className="h-14 shrink-0 border-b border-border bg-shell" />
        ) : null}
        {guest ? <GuestHeader compact={isMobile} /> : null}
        {showSidebar && isMobile ? (
          <Suspense
            fallback={<div aria-hidden="true" className="h-14 border-b border-border bg-shell" />}
          >
            <MobileSidebar
              viewer={viewer}
              account={account}
              open={mobileOpen}
              onOpenChange={(open) => {
                setMenuPath(open ? pathname : null)
              }}
              onSearch={openSearch}
            />
          </Suspense>
        ) : null}
        <PageMain />
      </div>
      {searchMounted ? (
        <Suspense fallback={null}>
          <SearchDialog open={searchOpen} onOpenChange={setSearchOpen} viewer={viewer} />
        </Suspense>
      ) : null}
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
