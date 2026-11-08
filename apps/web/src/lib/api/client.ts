/**
 * O cliente tipado da API: a porta do frontend para o servidor, fora o
 * fluxo SSE de `lib/sse.ts` (seções 6.6 e 13.2).
 *
 * O `openapi-fetch` monta cada pedido a partir dos tipos de `schema.ts`,
 * gerados do OpenAPI da API. `api.GET("/v1/me")` só aceita caminhos que
 * existem, confere parâmetros e corpo, e devolve `{ data, error, response }`
 * com os tipos da resposta. Um HTTP 4xx ou 5xx não lança erro: quem chama
 * olha `response.ok` ou `error`. Uma falha de rede, sim, rejeita a
 * promessa.
 *
 * Todo pedido vai para `/backend`, na mesma origem da página. Local, o
 * proxy do Vite (`vite.config.ts`) tira o prefixo e leva à API em
 * `127.0.0.1:8000`. Na Vercel, a rota de `vercel.ts` leva à API na
 * Railway, com o segredo da borda (seção 10.3). Na mesma origem, o cookie
 * de sessão é da página, e o tráfego normal não precisa de CORS (ADR-001).
 *
 * Quem usa: os hooks de `features` (arquivos `use*.ts`), únicos lugares
 * fora de `lib` onde o ESLint deixa importar esta pasta (seção 6.2).
 */
import createClient from "openapi-fetch"

import type { paths } from "./schema.ts"

/**
 * A base de todo pedido: a origem da página mais `/backend`.
 *
 * Precisa ser absoluta, porque o `openapi-fetch` cria um `Request`, e fora
 * do navegador o `Request` recusa URL relativa. Sem `window`, como no
 * projeto `node` do Vitest, ou com origem opaca, que o navegador escreve
 * como o texto `"null"`, vale `http://127.0.0.1/backend`. A base é lida uma
 * vez, quando o módulo carrega.
 */
function apiBaseUrl(): string {
  if (typeof window === "undefined" || window.location.origin === "null") {
    return "http://127.0.0.1/backend"
  }
  return `${window.location.origin}/backend`
}

/**
 * O cliente único. `credentials: "include"` manda os cookies
 * `atrium_session` e `atrium_guest` (seção 10.3) em todo pedido.
 *
 * O `fetch` passa por uma função que lê `globalThis.fetch` a cada pedido.
 * Sem ela, o `openapi-fetch` guardaria o `fetch` que existia ao criar o
 * cliente, e o `vi.stubGlobal("fetch", ...)` dos testes não o trocaria.
 */
export const api = createClient<paths>({
  baseUrl: apiBaseUrl(),
  credentials: "include",
  fetch: (request) => globalThis.fetch(request),
})
