import { act, render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import axe from "axe-core"
import { createMemoryRouter, RouterProvider } from "react-router"
import { describe, expect, it, vi } from "vitest"

import { routes } from "@/app/router.tsx"
import { AppProviders } from "@/app/providers.tsx"
import { pt } from "@/i18n/pt.ts"
import { gsap } from "@/motion/gsap.ts"

const publicPages = [
  ["/", pt.home.title],
  ["/ask", pt.pages.ask],
  ["/ask/visita", pt.pages.ask],
  ["/register", pt.pages.register],
  ["/register/form", pt.pages.registerForm],
  ["/sign-in", pt.pages.signIn],
  ["/privacy", pt.pages.privacy],
  ["/terms", pt.pages.terms],
] as const

const protectedPages = [
  ["/account", pt.pages.account],
  ["/legal/accept", pt.pages.legalAccept],
  ["/admin", pt.pages.admin],
  ["/admin/documents", pt.pages.documents],
  ["/admin/quality", pt.pages.quality],
  ["/admin/privacy", pt.pages.privacyRequests],
] as const

const member = {
  id: "00000000-0000-4000-8000-0000000000a1",
  email: "ana@example.com",
  full_name: "Ana Costa",
  phone: null,
  visitor_type: null,
  visit_reason: null,
  role: "member",
  needs_legal_acceptance: false,
}

function signIn() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const request =
        input instanceof Request ? input : new Request(String(input))
      if (new URL(request.url).pathname.endsWith("/v1/me")) {
        return new Response(JSON.stringify(member), {
          status: 200,
          headers: { "content-type": "application/json" },
        })
      }
      return new Response(null, { status: 404 })
    })
  )
}

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  const view = render(
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  )
  return { router, ...view }
}

describe("casca", () => {
  it.each(publicPages)("foca o título ao abrir %s", async (path, title) => {
    const start = path === "/" ? "/sign-in" : "/"
    const { router } = renderAt(start)
    await screen.findByRole("heading", { level: 1 })
    await act(async () => {
      await router.navigate(path)
    })
    const heading = await screen.findByRole("heading", {
      level: 1,
      name: title,
    })
    await waitFor(() => {
      expect(document.activeElement).toBe(heading)
    })
    expect(document.title).toBe(`${title} · ${pt.appName}`)
  })

  it.each(protectedPages)(
    "sem sessão, %s volta para entrar e guarda o retorno",
    async (path) => {
      const { router } = renderAt("/")
      await screen.findByRole("heading", { level: 1, name: pt.home.title })
      await act(async () => {
        await router.navigate(path)
      })
      const heading = await screen.findByRole("heading", {
        level: 1,
        name: pt.pages.signIn,
      })
      await waitFor(() => {
        expect(document.activeElement).toBe(heading)
      })
      expect(router.state.location.pathname).toBe("/sign-in")
      expect(router.state.location.search).toBe(
        `?returnTo=${encodeURIComponent(path)}`
      )
    }
  )

  it("sem sessão, mostra entrar e cadastros no lugar da barra lateral", async () => {
    renderAt("/")
    const nav = await screen.findByRole("navigation", {
      name: pt.sidebar.guestMenu,
    })
    expect(
      within(nav).getByRole("link", { name: pt.nav.signIn })
    ).toHaveAttribute("href", "/sign-in")
    expect(
      within(nav).getByRole("link", { name: pt.nav.registerForm })
    ).toHaveAttribute("href", "/register/form")
    expect(
      within(nav).getByRole("link", { name: pt.nav.registerWithAi })
    ).toHaveAttribute("href", "/register")
    expect(
      screen.queryByRole("navigation", { name: pt.sidebar.label })
    ).not.toBeInTheDocument()
  })

  it("sem sessão no celular, o menu traz entrar e cadastros", async () => {
    window.__media = {
      "(prefers-reduced-motion: reduce)": true,
      "(min-width: 1024px)": false,
      "(max-width: 767px)": true,
    }
    const user = userEvent.setup()
    renderAt("/")
    await user.click(
      await screen.findByRole("button", { name: pt.sidebar.guestMenu })
    )
    expect(
      await screen.findByRole("menuitem", { name: pt.nav.registerWithAi })
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: pt.sidebar.openMenu })
    ).not.toBeInTheDocument()
  })

  it("com sessão de membro, a barra lateral não mostra cadastro nem operação", async () => {
    signIn()
    renderAt("/")
    const nav = await screen.findByRole("navigation", {
      name: pt.sidebar.label,
    })
    expect(
      within(nav).queryByRole("link", { name: pt.nav.signIn })
    ).not.toBeInTheDocument()
    expect(
      within(nav).queryByRole("link", { name: pt.nav.overview })
    ).not.toBeInTheDocument()
    expect(
      within(nav).getByRole("link", { name: pt.nav.privacy })
    ).toBeInTheDocument()
  })

  it("abre o menu no celular", async () => {
    signIn()
    window.__media = {
      "(prefers-reduced-motion: reduce)": true,
      "(min-width: 1024px)": false,
      "(max-width: 767px)": true,
    }
    const user = userEvent.setup()
    renderAt("/")
    await user.click(
      await screen.findByRole("button", { name: pt.sidebar.openMenu })
    )
    expect(await screen.findByRole("dialog")).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: pt.nav.privacy })
    ).toBeInTheDocument()
  })

  it("mostra o link para pular ao conteúdo", async () => {
    renderAt("/")
    expect(
      await screen.findByRole("link", { name: pt.skipToContent })
    ).toHaveAttribute("href", "#conteudo")
  })

  it("recolhe a barra e abre uma rota pelo menu", async () => {
    signIn()
    const user = userEvent.setup()
    renderAt("/")
    await screen.findByRole("navigation", { name: pt.sidebar.label })
    await user.click(screen.getByRole("button", { name: pt.sidebar.collapse }))
    expect(
      screen.getByRole("button", { name: pt.sidebar.expand })
    ).toBeInTheDocument()
    await user.click(screen.getByRole("link", { name: pt.nav.privacy }))
    expect(
      await screen.findByRole("heading", { name: pt.pages.privacy })
    ).toHaveFocus()
  })

  it("grava a preferência de movimento e atualiza o matchMedia", async () => {
    const user = userEvent.setup()
    const refresh = vi.spyOn(gsap, "matchMediaRefresh")
    signIn()
    renderAt("/")
    await screen.findByRole("navigation", { name: pt.sidebar.label })
    await user.click(screen.getByRole("button", { name: pt.profile.menu }))
    await user.click(
      screen.getByRole("menuitemradio", { name: pt.profile.motionReduce })
    )
    expect(localStorage.getItem("atrium.motion-preference")).toBe("on")
    expect(refresh).toHaveBeenCalled()
  })

  it("não tem violação grave ou crítica de acessibilidade", async () => {
    const { container } = renderAt("/")
    await screen.findByRole("heading", { name: pt.home.title })
    const results = await axe.run(container, { resultTypes: ["violations"] })
    const serious = results.violations.filter(
      (violation) =>
        violation.impact === "serious" || violation.impact === "critical"
    )
    expect(serious.map((violation) => violation.id)).toEqual([])
  })
})
