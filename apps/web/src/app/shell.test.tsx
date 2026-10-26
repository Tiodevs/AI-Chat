import { act, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import axe from "axe-core"
import { createMemoryRouter, RouterProvider } from "react-router"
import { describe, expect, it, vi } from "vitest"

import { routes } from "@/app/router.tsx"
import { AppProviders } from "@/app/providers.tsx"
import { pt } from "@/i18n/pt.ts"
import { gsap } from "@/motion/gsap.ts"

const pages = [
  ["/", pt.pages.home],
  ["/ask", pt.pages.ask],
  ["/ask/visita", pt.pages.ask],
  ["/register", pt.pages.register],
  ["/register/form", pt.pages.registerForm],
  ["/sign-in", pt.pages.signIn],
  ["/account", pt.pages.account],
  ["/privacy", pt.pages.privacy],
  ["/terms", pt.pages.terms],
  ["/legal/accept", pt.pages.legalAccept],
  ["/admin", pt.pages.admin],
  ["/admin/documents", pt.pages.documents],
  ["/admin/quality", pt.pages.quality],
  ["/admin/privacy", pt.pages.privacyRequests],
] as const

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  const view = render(
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>,
  )
  return { router, ...view }
}

describe("casca", () => {
  it.each(pages)("foca o título ao abrir %s", async (path, title) => {
    const start = path === "/" ? "/sign-in" : "/"
    const { router } = renderAt(start)
    await screen.findByRole("heading", { level: 1 })
    await act(async () => {
      await router.navigate(path)
    })
    const heading = await screen.findByRole("heading", { level: 1, name: title })
    await waitFor(() => {
      expect(document.activeElement).toBe(heading)
    })
    expect(document.title).toBe(`${title} · ${pt.appName}`)
  })

  it("abre o menu no celular", async () => {
    window.__media = {
      "(prefers-reduced-motion: reduce)": true,
      "(min-width: 1024px)": false,
      "(max-width: 767px)": true,
    }
    const user = userEvent.setup()
    renderAt("/")
    await user.click(
      await screen.findByRole("button", { name: pt.sidebar.openMenu }),
    )
    expect(await screen.findByRole("dialog")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: pt.nav.privacy })).toBeInTheDocument()
  })

  it("mostra o link para pular ao conteúdo", async () => {
    renderAt("/")
    expect(
      await screen.findByRole("link", { name: pt.skipToContent }),
    ).toHaveAttribute("href", "#conteudo")
  })

  it("recolhe a barra e abre uma rota pelo menu", async () => {
    const user = userEvent.setup()
    renderAt("/")
    await screen.findByRole("heading", { name: pt.pages.home })
    await user.click(screen.getByRole("button", { name: pt.sidebar.collapse }))
    expect(
      screen.getByRole("button", { name: pt.sidebar.expand }),
    ).toBeInTheDocument()
    await user.click(screen.getByRole("link", { name: pt.nav.privacy }))
    expect(
      await screen.findByRole("heading", { name: pt.pages.privacy }),
    ).toHaveFocus()
  })

  it("grava a preferência de movimento e atualiza o matchMedia", async () => {
    const user = userEvent.setup()
    const refresh = vi.spyOn(gsap, "matchMediaRefresh")
    renderAt("/account")
    await screen.findByRole("heading", { name: pt.pages.account })
    await user.click(screen.getByRole("button", { name: pt.profile.menu }))
    await user.click(
      screen.getByRole("menuitemradio", { name: pt.profile.motionReduce }),
    )
    expect(localStorage.getItem("atrium.motion-preference")).toBe("on")
    expect(refresh).toHaveBeenCalled()
  })

  it("não tem violação grave ou crítica de acessibilidade", async () => {
    const { container } = renderAt("/")
    await screen.findByRole("heading", { name: pt.pages.home })
    const results = await axe.run(container, { resultTypes: ["violations"] })
    const serious = results.violations.filter(
      (violation) => violation.impact === "serious" || violation.impact === "critical",
    )
    expect(serious.map((violation) => violation.id)).toEqual([])
  })
})
