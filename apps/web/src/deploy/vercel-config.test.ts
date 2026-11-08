/**
 * O `vercel.ts` declara só `routes`, com o segredo da borda apenas na rota da
 * API e as rotas na ordem que a Vercel gerava. Seções 10.3, 13.4 e 22.2 do
 * SDD.
 *
 * Importa a configuração de verdade, com uma `API_URL` de teste, e compara a
 * lista com a saída do `getTransformedRoutes` da `@vercel/routing-utils`
 * 6.6.0 para os `rewrites` e `headers` de antes da Etapa 12.5. A saída está
 * copiada no teste: ele não chama a biblioteca. Os cabeçalhos de segurança
 * vêm do mesmo `security-headers.ts` que o `vite preview` usa. Roda no
 * projeto `node` do Vitest. Não usa a API, a rede nem banco.
 */
import { beforeAll, describe, expect, it } from "vitest"

import { securityHeaders } from "../../security-headers.ts"

type Route = Record<string, unknown>

/** Origem falsa da API, só para o `vercel.ts` montar o destino da rota. */
const API = "https://api.example.test"
/** Regex de `/backend/:path*` como `plain` a deixa, sem escapar as barras. */
const BACKEND_SRC = "^/backend(?:/((?:[^/]+?)(?:/(?:[^/]+?))*))?$"

let keys: string[] = []
let routes: Route[] = []

// O `vercel.ts` monta as rotas ao carregar e falha sem uma `API_URL` https
// (seção 13.4). Por isso a variável entra antes da importação dinâmica.
beforeAll(async () => {
  process.env.API_URL = API
  const { config } = await import("../../vercel.ts")
  keys = Object.keys(config)
  routes = (config.routes ?? []) as Route[]
})

/** A regex da rota da API sai com as barras escapadas; `\/` e `/` casam o mesmo caminho. */
function plain(route: Route): Route {
  const copy = Object.fromEntries(Object.entries(route).filter(([key]) => key !== "transforms"))
  if (typeof copy.src === "string") {
    copy.src = copy.src.replaceAll("\\/", "/")
  }
  return copy
}

/** As rotas cuja regex `src` casa com `path`, na ordem da configuração. */
function matching(path: string): Route[] {
  return routes.filter((route) => typeof route.src === "string" && new RegExp(route.src).test(path))
}

describe("configuração da Vercel (seções 10.3, 13.4 e 22.2)", () => {
  it("usa só routes, porque a CLI recusa routes junto com rewrites, redirects ou headers", () => {
    expect(keys).toContain("routes")
    expect(keys).not.toContain("rewrites")
    expect(keys).not.toContain("redirects")
    expect(keys).not.toContain("headers")
  })

  it("a rota da API troca o cabeçalho da borda pelo EDGE_SECRET do ambiente", () => {
    const backend = routes.find((route) => route.dest === `${API}/$1`)
    expect(backend?.transforms).toEqual([
      {
        type: "request.headers",
        op: "set",
        target: { key: "x-atrium-edge" },
        args: "$EDGE_SECRET",
        env: ["EDGE_SECRET"],
      },
    ])
    expect(routes.filter((route) => "transforms" in route)).toHaveLength(1)
  })

  it("mantém as rotas que a Vercel gerava dos rewrites e headers de antes", () => {
    // Saída do getTransformedRoutes da @vercel/routing-utils 6.6.0 para os rewrites e headers
    // anteriores à Etapa 12.5: cabeçalhos com continue, filesystem e, por fim, os rewrites.
    expect(routes.map(plain)).toEqual([
      { src: BACKEND_SRC, headers: { "x-vercel-enable-rewrite-caching": "0" }, continue: true },
      { src: "^(?:/(.*))$", headers: securityHeaders, continue: true },
      {
        src: "^/assets(?:/(.*))$",
        headers: { "Cache-Control": "public, max-age=31536000, immutable" },
        continue: true,
      },
      {
        src: "^(?:/((?!assets/|backend/).*))$",
        headers: { "Cache-Control": "no-cache" },
        continue: true,
      },
      { handle: "filesystem" },
      { src: BACKEND_SRC, dest: `${API}/$1`, check: true },
      { src: "^(?:/((?!backend/|assets/).*))$", dest: "/index.html", check: true },
    ])
  })

  it("leva /backend à API e as rotas da SPA ao index.html, fora de /assets", () => {
    expect(matching("/backend/v1/conversations").map((route) => route.dest)).toContain(`${API}/$1`)
    expect(matching("/privacy").map((route) => route.dest)).toContain("/index.html")
    expect(matching("/assets/nao-existe.js").map((route) => route.dest)).not.toContain(
      "/index.html",
    )
  })
})
