/**
 * Configuração da Vercel. Seções 10.3, 13.4, 22.2 e 22.3 do SDD.
 *
 * `API_URL` é lida no build: cada ambiente aponta para a sua API na Railway. O navegador fala
 * só com a origem da Vercel, e o rewrite leva `/backend/*` para a API (ADR-001). A publicação
 * por Git fica desligada, porque o GitHub Actions publica (ADR-008).
 *
 * O arquivo é TypeScript, com os tipos e os ajudantes do `@vercel/config`.
 * O `vercel build` do `deploy.yml` o compila, e o resultado faz o papel de
 * um `vercel.json`.
 *
 * As rotas valem na ordem. As de cabeçalho têm `continue`: juntam os
 * cabeçalhos e deixam o pedido seguir. `handle: filesystem` serve o
 * arquivo do build quando ele existe. Depois vêm a rota da API e o
 * fallback da SPA, que entrega o `index.html` a qualquer outro caminho
 * para o React Router resolver no navegador.
 *
 * Quem usa: o `vercel build` e o teste `src/deploy/vercel-config.test.ts`,
 * que trava a lista de rotas. Usa `security-headers.ts`. O bloco de código
 * da seção 13.4 ainda mostra o formato antigo, com `rewrites`; a seção
 * 22.2 descreve o atual, só com `routes`.
 */
import { deploymentEnv, routes, type VercelConfig } from "@vercel/config/v1"

import { securityHeaders } from "./security-headers.ts"

/**
 * A origem da API do ambiente, lida de `API_URL` na hora do build.
 *
 * Exige `https:` e só a origem: sem caminho, busca, fragmento, usuário nem
 * senha. Um valor ausente ou fora disso lança erro e falha o build da
 * Vercel (seção 13.4).
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

/** Cabeçalho com o segredo que só a Vercel e a API conhecem (seção 10.3). */
export const EDGE_HEADER = "x-atrium-edge"

/**
 * O rewrite da API, com o segredo da borda. O `set` troca qualquer valor que o visitante mande,
 * e a Vercel lê `EDGE_SECRET` do ambiente da implantação na hora do pedido: o valor não passa
 * pelo código nem pelo build.
 *
 * `:path*` captura o resto do caminho: `/backend/v1/me` vai para
 * `API_URL/v1/me`. Com `requestHeaders`, o `routes.rewrite` não sai como
 * item de `rewrites`, e sim como uma rota de baixo nível, com `src`,
 * `dest` e um `transform`. A checagem garante esse formato.
 */
function backendRoute() {
  const route = routes.rewrite("/backend/:path*", `${apiUrl()}/:path*`, {
    requestHeaders: { [EDGE_HEADER]: deploymentEnv("EDGE_SECRET") },
  })
  if (!("src" in route)) {
    throw new Error("O rewrite de /backend com o segredo precisa sair no formato routes.")
  }
  // `check` é o que a Vercel põe em todo rewrite convertido de `rewrites`.
  return { ...route, check: true }
}

// A rota nasce quando o módulo carrega: sem `API_URL`, importar este
// arquivo já falha. O teste define `API_URL` antes do import.
const backend = backendRoute()

export const config: VercelConfig = {
  framework: "vite",
  // As versões do `pnpm-lock.yaml`, sem atualizar nada.
  installCommand: "pnpm install --frozen-lockfile",
  // `tsc -b` e `vite build`, pelo script do `package.json`.
  buildCommand: "pnpm build",
  outputDirectory: "dist",
  git: { deploymentEnabled: false },
  // O cabeçalho do segredo só existe no formato `routes`, e a CLI da Vercel recusa `routes`
  // junto com `rewrites` ou `headers`. Estas são as rotas que a Vercel gerava dos `rewrites` e
  // `headers` de antes, na mesma ordem: cabeçalhos com `continue`, os arquivos do build e, por
  // fim, os rewrites. Só a rota da API mudou, com o segredo.
  routes: [
    // Respostas da API nunca ficam no cache da Vercel (a API já manda no-store).
    {
      src: backend.src,
      headers: { "x-vercel-enable-rewrite-caching": "0" },
      continue: true,
    },
    // Os cabeçalhos de segurança da seção 13.4, em todo caminho.
    { src: "^(?:/(.*))$", headers: securityHeaders, continue: true },
    // Os arquivos do build têm hash no nome: um conteúdo novo ganha um nome
    // novo, e o cache de um ano não serve versão velha.
    {
      src: "^/assets(?:/(.*))$",
      headers: { "Cache-Control": "public, max-age=31536000, immutable" },
      continue: true,
    },
    // O index.html (e as rotas da SPA que caem nele) é sempre revalidado.
    {
      src: "^(?:/((?!assets/|backend/).*))$",
      headers: { "Cache-Control": "no-cache" },
      continue: true,
    },
    // Um arquivo que existe no build é servido aqui, e a busca de rota para.
    { handle: "filesystem" },
    backend,
    // As rotas da SPA caem no index.html. /assets fica de fora: um arquivo ausente responde
    // 404, em vez de devolver o index.html com o cache de um ano dos arquivos com hash.
    { src: "^(?:/((?!backend/|assets/).*))$", dest: "/index.html", check: true },
  ],
}
