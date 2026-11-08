/**
 * A árvore de rotas do app, no modo de dados do React Router.
 *
 * No modo de dados, o roteador conhece a árvore inteira antes de
 * renderizar: casa a URL, baixa os módulos das rotas e roda os `loader`, e
 * só então mostra a página. Numa navegação, a página atual fica na tela até
 * a próxima estar pronta.
 *
 * Cada página carrega sob demanda: `lazy` importa o módulo da rota só
 * quando a URL casa com ela, e o React Router lê dele o `Component` e o
 * `ErrorBoundary`. As três rotas que abrem `/` (casca, moldura e início)
 * também vão como `modulepreload` no `index.html`, pelo plugin
 * `route-preload.ts` (seções 5.3 e 13.1).
 *
 * Os guards de `guards.ts` entram como `loader`. Por estar fora do `lazy`,
 * o `loader` roda ao mesmo tempo que o download do módulo da página.
 *
 * Quem usa: `main.tsx` (`router`) e `shell.test.tsx` (`routes`, num
 * roteador em memória). SDD 13.1, 13.3 e 15.4.
 */
import { createBrowserRouter, type RouteObject } from "react-router"

import { requireAdmin, requireSession, requireUser } from "@/app/guards.ts"
import { pt } from "@/i18n/pt.ts"

/**
 * O que aparece na primeira carga, enquanto o roteador baixa os módulos da
 * rota pedida e roda os `loader`. Nas navegações seguintes ele não volta.
 */
function ShellFallback() {
  return <p className="p-6 text-body text-muted-foreground">{pt.loading}</p>
}

/**
 * A árvore das rotas da seção 15.4, sem roteador. Os testes a montam com
 * `createMemoryRouter`, que guarda a URL na memória.
 */
export const routes: RouteObject[] = [
  {
    // A casca é a rota raiz: barra lateral ou cabeçalho, e o `main` onde as
    // páginas aparecem. Ela não tem `ErrorBoundary` e não há rota `*`: um
    // erro na casca ou uma URL sem rota caem na tela de erro padrão do
    // React Router, em inglês. A Etapa 14.1 cria a página não encontrada e
    // o `ErrorBoundary` na raiz.
    path: "/",
    HydrateFallback: ShellFallback,
    lazy: () => import("./shell.tsx"),
    children: [
      {
        // Rota sem `path`: não muda a URL, só envolve as páginas. O
        // `ErrorBoundary` dela mostra os erros das páginas dentro da casca.
        lazy: () => import("./route-frame.tsx"),
        children: [
          { index: true, lazy: () => import("./routes/home.tsx") },
          // O `?` deixa o `id` opcional: `/ask` e `/ask/:id` usam o mesmo
          // módulo.
          { path: "ask/:id?", lazy: () => import("./routes/ask.tsx") },
          { path: "register", lazy: () => import("./routes/register.tsx") },
          {
            path: "register/form",
            lazy: () => import("./routes/register-form.tsx"),
          },
          { path: "sign-in", lazy: () => import("./routes/sign-in.tsx") },
          {
            // Sessão e aceite em dia.
            path: "account",
            lazy: () => import("./routes/account.tsx"),
            loader: requireUser,
          },
          { path: "privacy", lazy: () => import("./routes/privacy.tsx") },
          { path: "terms", lazy: () => import("./routes/terms.tsx") },
          {
            // Só a sessão: esta é a tela que resolve o aceite pendente.
            path: "legal/accept",
            lazy: () => import("./routes/legal-accept.tsx"),
            loader: requireSession,
          },
          // As quatro rotas de admin: sessão, aceite e `role` admin. Outro
          // papel recebe a página 403 da moldura.
          {
            path: "admin",
            lazy: () => import("./routes/admin.tsx"),
            loader: requireAdmin,
          },
          {
            path: "admin/documents",
            lazy: () => import("./routes/admin-documents.tsx"),
            loader: requireAdmin,
          },
          {
            path: "admin/quality",
            lazy: () => import("./routes/admin-quality.tsx"),
            loader: requireAdmin,
          },
          {
            path: "admin/privacy",
            lazy: () => import("./routes/admin-privacy.tsx"),
            loader: requireAdmin,
          },
        ],
      },
    ],
  },
]

/**
 * O roteador do navegador: lê e muda a URL pela History API. Nasce uma vez,
 * quando o módulo carrega, e `main.tsx` o entrega ao `RouterProvider`.
 */
export const router = createBrowserRouter(routes)
