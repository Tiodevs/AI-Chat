import { cleanup } from "@testing-library/react"
import "@testing-library/jest-dom/vitest"
import { afterEach, beforeEach, vi } from "vitest"

import { queryClient } from "@/app/query-client.ts"
import { resetAskState } from "@/features/ask/store.ts"

declare global {
  interface Window {
    __media?: Record<string, boolean>
  }
}

function queryMatches(query: string) {
  return window.__media?.[query] ?? false
}

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
  vi.unstubAllGlobals()
})

beforeEach(() => {
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
