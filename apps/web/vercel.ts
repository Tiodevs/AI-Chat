import { routes, type VercelConfig } from "@vercel/config/v1"

import { securityHeaders } from "./security-headers.ts"

/**
 * Configuração da Vercel. Seções 13.4, 22.2 e 22.3 do SDD.
 *
 * `API_URL` é lida no build: cada ambiente aponta para a sua API na Railway. O navegador fala
 * só com a origem da Vercel, e o rewrite leva `/backend/*` para a API (ADR-001). A publicação
 * por Git fica desligada, porque o GitHub Actions publica (ADR-008).
 */
function apiUrl(): string {
  const raw = process.env.API_URL?.trim() ?? ""
  const parsed = URL.canParse(raw) ? new URL(raw) : null
  const originOnly =
    parsed !== null &&
    parsed.protocol === "https:" &&
    parsed.pathname === "/" &&
    !parsed.search &&
    !parsed.hash &&
    !parsed.username &&
    !parsed.password
  if (!parsed || !originOnly) {
    throw new Error("Defina API_URL com a origem https da API, sem caminho, antes do build.")
  }
  return parsed.origin
}

const everyResponse = Object.entries(securityHeaders).map(([key, value]) => ({ key, value }))

export const config: VercelConfig = {
  framework: "vite",
  installCommand: "pnpm install --frozen-lockfile",
  buildCommand: "pnpm build",
  outputDirectory: "dist",
  git: { deploymentEnabled: false },
  rewrites: [
    routes.rewrite("/backend/:path*", `${apiUrl()}/:path*`),
    // As rotas da SPA caem no index.html. /assets fica de fora: um arquivo ausente responde
    // 404, em vez de devolver o index.html com o cache de um ano dos arquivos com hash.
    routes.rewrite("/((?!backend/|assets/).*)", "/index.html"),
  ],
  headers: [
    // Respostas da API nunca ficam no cache da Vercel (a API já manda no-store).
    routes.header("/backend/:path*", [{ key: "x-vercel-enable-rewrite-caching", value: "0" }]),
    routes.header("/(.*)", everyResponse),
    routes.header("/assets/(.*)", [
      { key: "Cache-Control", value: "public, max-age=31536000, immutable" },
    ]),
    // O index.html (e as rotas da SPA que caem nele) é sempre revalidado.
    routes.header("/((?!assets/|backend/).*)", [{ key: "Cache-Control", value: "no-cache" }]),
  ],
}
