/**
 * A casca do app: a rota raiz, em volta de todas as páginas.
 *
 * Com sessão, mostra a barra lateral; no celular, a barra do topo com o
 * menu em sheet. Sem sessão, mostra o `GuestHeader`. Abaixo vem o `main`,
 * com a entrada da página nova (M1) e o foco no título (seção 15.8). A
 * casca também tem o link para pular ao conteúdo e o atalho ⌘K da busca.
 *
 * Quem usa: `router.tsx`, por `lazy`; o arquivo vai como `modulepreload`
 * no `index.html`. Usa o `meQuery` (`GET /v1/me`) para saber quem vê, o
 * `useSignOut`, o `useMotion` para a largura da tela e o movimento
 * reduzido, e o preset `enterRoute`. SDD 13.1, 14.5, 15.8 e 16.3.
 */
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
// O `lazy` do React só aceita um módulo com export `default`: o `then`
// entrega o componente nomeado nesse formato. As duas barras vêm do mesmo
// arquivo, que o navegador baixa uma vez só.
const AppSidebar = lazy(() => loadSidebar().then((module) => ({ default: module.AppSidebar })))
const MobileSidebar = lazy(() =>
  loadSidebar().then((module) => ({ default: module.MobileSidebar })),
)
const loadSearch = () => import("@/components/patterns/search-dialog.tsx")
const SearchDialog = lazy(() => loadSearch().then((module) => ({ default: module.SearchDialog })))

/**
 * Reserva o espaço da barra lateral enquanto ela carrega, sem deslocar o
 * conteúdo: 64 px recolhida e 240 px aberta, as larguras da seção 14.5.
 */
function SidebarPlaceholder({ collapsed }: { collapsed: boolean }) {
  return (
    <div
      aria-hidden="true"
      className={cn("h-full shrink-0 border-r border-border bg-shell", collapsed ? "w-16" : "w-60")}
    />
  )
}

/**
 * A página da rota atual, com a entrada M1 e o foco no título.
 *
 * `useOutlet` devolve o elemento da rota filha. A `key={pathname}` recria o
 * invólucro a cada caminho novo, e o `useGSAP` anima o conteúdo que acabou
 * de montar. Na primeira página, a da carga do app, não há animação nem
 * foco: a pessoa começa no topo do documento, onde fica o link para pular
 * ao conteúdo.
 */
function RouteTransition() {
  const outlet = useOutlet()
  const { pathname } = useLocation()
  const rootRef = useRef<HTMLDivElement>(null)
  // Os dois marcam a primeira montagem: um para o `useGSAP`, outro para o
  // `useEffect`. Cada um consome o seu.
  const skipFocus = useRef(true)
  const skipFocusEffect = useRef(true)
  const { reduced } = useMotion()

  // Foco no título logo depois da troca de rota. Se o título está
  // invisível pela entrada M1, o `focus` não pega, e o `onComplete` abaixo
  // tenta de novo no fim da animação.
  useEffect(() => {
    if (skipFocusEffect.current) {
      skipFocusEffect.current = false
      return
    }
    focusPageTitle()
  }, [pathname])

  // `scope` limita os seletores e o desfazer das animações ao invólucro
  // (seção 16.5). As dependências rodam a entrada a cada caminho novo e
  // quando o movimento reduzido muda.
  useGSAP(
    () => {
      const root = rootRef.current
      if (!root) {
        return
      }
      // Com cards marcados por `data-motion-card`, eles entram um a um com
      // `stagger.list` (M1). Sem cards, entra o invólucro inteiro.
      const cards = root.querySelectorAll("[data-motion-card]")
      const target = cards.length > 0 ? cards : root
      const skip = skipFocus.current
      skipFocus.current = false
      // Na primeira página, `skip` usa o caminho direto do preset.
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

/**
 * A moldura de todas as telas, com as regiões da seção 14.5.
 *
 * 1. Lê `GET /v1/me` pelo `meQuery`. Até a resposta chegar, não aparece
 *    nem a barra lateral nem o `GuestHeader`; no celular, uma barra de
 *    56 px segura o lugar.
 * 2. Sem sessão, mostra o `GuestHeader`. Com sessão, a barra lateral, que
 *    carrega sob demanda: a `AppSidebar` no desktop e no tablet, e a
 *    `MobileSidebar`, com o menu em sheet, no celular.
 * 3. Monta a busca (`SearchDialog`) na primeira abertura, pelo botão ou
 *    pelo ⌘K. No desktop, baixa o arquivo antes, no tempo ocioso.
 *
 * Efeitos colaterais: rede (`GET /v1/me` e, ao sair,
 * `POST /v1/auth/logout`), um ouvinte de `keydown` na janela e o
 * download antecipado da busca.
 */
export function AppShell() {
  const { isDesktop, isMobile } = useMotion()
  // `null` até a pessoa usar o botão de recolher. Até lá, a barra segue a
  // tela: recolhida fora do desktop, em 64 px no tablet (seção 14.5).
  const [collapsedChoice, setCollapsedChoice] = useState<boolean | null>(null)
  const collapsed = collapsedChoice ?? !isDesktop
  // `searchMounted` baixa e monta a busca na primeira vez; `searchOpen` só
  // abre e fecha. Depois de montada, ela continua montada.
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchMounted, setSearchMounted] = useState(false)
  // O menu do celular fica aberto só no caminho em que abriu: ao navegar,
  // `mobileOpen` vira falso sem precisar de efeito.
  const [menuPath, setMenuPath] = useState<string | null>(null)
  const { pathname } = useLocation()
  const mobileOpen = menuPath === pathname
  const me = useQuery(meQuery)
  const viewer = viewerOf(me.data?.role)
  // Enquanto `me` carrega, a pessoa não conta como visitante nem como
  // membro: nenhuma das duas navegações aparece até a resposta dizer qual.
  const guest = !me.isPending && viewer === "guest"
  const showSidebar = !me.isPending && !guest
  const signOut = useSignOut()
  // O que o `ProfileButton` mostra: o primeiro nome (seção 14.6) e a saída.
  // Um nome que começa com espaço dá um primeiro pedaço vazio, e vale o
  // nome inteiro.
  const account = me.data
    ? {
        name: me.data.full_name.split(" ")[0] || me.data.full_name,
        onSignOut: () => {
          // Ninguém espera a promessa: o erro já vira `signOutError` dentro
          // do hook.
          void signOut.signOut()
        },
        signingOut: signOut.pending,
        signOutError: signOut.error,
      }
    : undefined

  /** Abre a busca, montando-a na primeira vez. */
  function openSearch() {
    setSearchMounted(true)
    setSearchOpen(true)
  }

  // No desktop, a paleta chega quando o navegador fica livre, para o ⌘K abrir sem espera. No
  // celular não há atalho de teclado: ela só baixa quando alguém abre a busca, e a rede móvel
  // do visitante fica para a primeira tela (seção 5.3).
  useEffect(() => {
    if (isMobile) {
      return
    }
    const prefetch = () => {
      void loadSearch()
    }
    // `timeout: 4000` força o download em até 4 s, mesmo com o navegador
    // ocupado. Sem `requestIdleCallback`, um `setTimeout` de 2 s faz o papel.
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
  }, [isMobile])

  // ⌘K no Mac e Ctrl+K nos outros sistemas abrem a busca (seção 15.8).
  // `toLowerCase` aceita a tecla com Shift ou Caps Lock, `repeat` ignora a
  // tecla segurada e `preventDefault` tira a ação do próprio navegador.
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
      {/* O link para pular ao conteúdo (seção 15.8) só aparece com foco:
          `sr-only` o esconde e `focus:not-sr-only` o mostra. Ele leva ao
          `main` de id `conteudo`. */}
      <a
        href="#conteudo"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
      >
        {pt.skipToContent}
      </a>
      {/* Desktop e tablet. O espaço reservado tem a largura da barra
          enquanto o arquivo dela baixa (CLS, seção 5.3). */}
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
        {/* Celular com sessão: a mesma barra de 56 px segura o topo
            enquanto o arquivo da barra lateral baixa. */}
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
      {/* A busca só entra na árvore depois da primeira abertura. Um
          diálogo não ocupa lugar na página, então o `fallback` é vazio. */}
      {searchMounted ? (
        <Suspense fallback={null}>
          <SearchDialog open={searchOpen} onOpenChange={setSearchOpen} viewer={viewer} />
        </Suspense>
      ) : null}
    </div>
  )
}

/**
 * A região principal, alvo do link para pular ao conteúdo. É ela que rola,
 * e não a janela: a casca ocupa a altura da tela (`h-dvh`) com
 * `overflow-hidden`. `tabIndex={-1}` deixa o `main` receber o foco do
 * link. O conteúdo vai até 1280 px (`max-w-7xl`), com padding de 16, 20 e
 * 24 px do celular ao desktop (seção 14.5).
 */
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

/** O componente da rota raiz, que o `lazy` de `router.tsx` lê do módulo. */
export function Component() {
  return <AppShell />
}
