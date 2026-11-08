/**
 * A preparação de todo teste do projeto `dom` do Vitest, o das telas e
 * componentes, que roda no jsdom (`vite.config.ts`, `setupFiles`).
 *
 * O jsdom não tem `matchMedia` nem `ResizeObserver`: o arquivo instala
 * versões falsas. Antes de cada teste, força movimento reduzido e a tela
 * de desktop (seção 16.5) e troca o `fetch` por uma resposta 401: um pedido
 * que o teste não simulou se comporta como visitante sem sessão e não sai
 * para a rede. Depois de cada teste, limpa a tela, o cache do TanStack
 * Query e o estado da conversa, objetos únicos de módulo que passariam de
 * um teste para o seguinte. Seção 21.1 do SDD.
 */
import { cleanup, configure } from "@testing-library/react"
// Os matchers de DOM, como `toBeInTheDocument` e `toHaveFocus`.
import "@testing-library/jest-dom/vitest"
import { afterEach, beforeEach, vi } from "vitest"

import { queryClient } from "@/app/query-client.ts"
import { resetAskState } from "@/features/ask/store.ts"

// `window.__media` diz quais media queries casam. Um teste o troca antes
// de montar a tela, como os do celular em `app/shell.test.tsx`.
declare global {
  interface Window {
    __media?: Record<string, boolean>
  }
}

/** Uma consulta fora de `window.__media` não casa. */
function queryMatches(query: string) {
  return window.__media?.[query] ?? false
}

/**
 * Um `matchMedia` falso, que lê `window.__media` a cada leitura de
 * `matches`. Os ouvintes não fazem nada: nenhuma mudança de tela chega ao
 * `gsap.matchMedia` do `MotionProvider` durante o teste, e vale o que ele
 * leu ao montar.
 */
function installMatchMedia() {
  window.matchMedia = ((query: string) => ({
    get matches() {
      return queryMatches(query)
    },
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  })) as typeof window.matchMedia
}

installMatchMedia()

// As rotas de admin carregam o Recharts sob demanda; sob carga, a importação passa de 1 s.
configure({ asyncUtilTimeout: 3000 })

// O Radix e o Recharts usam `ResizeObserver`. Esta versão não observa nada.
globalThis.ResizeObserver = class {
  observe() {
    return undefined
  }
  unobserve() {
    return undefined
  }
  disconnect() {
    return undefined
  }
} as typeof ResizeObserver

afterEach(() => {
  cleanup()
  queryClient.clear()
  resetAskState()
  // Desfaz o `fetch` falso e qualquer outro `vi.stubGlobal` do teste.
  vi.unstubAllGlobals()
})

beforeEach(() => {
  // Sem preferência gravada: o movimento segue o sistema, que aqui reduz.
  localStorage.clear()
  sessionStorage.clear()
  document.documentElement.lang = "pt-BR"
  document.documentElement.dataset.motion = "reduce"
  window.__media = {
    "(prefers-reduced-motion: reduce)": true,
    "(min-width: 1024px)": true,
    "(max-width: 767px)": false,
  }
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => unauthenticated())
  )
})

/**
 * A resposta da API sem sessão, no formato de erro da seção 12, com um
 * `request_id` fixo. É o que `GET /v1/me` devolve a um visitante.
 */
function unauthenticated() {
  return new Response(
    JSON.stringify({
      error: {
        code: "unauthenticated",
        message: "Entre para continuar.",
        request_id: "01TEST",
      },
    }),
    { status: 401, headers: { "content-type": "application/json" } }
  )
}
