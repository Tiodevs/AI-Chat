import { cleanup } from "@testing-library/react"
import "@testing-library/jest-dom/vitest"
import { afterEach, beforeEach } from "vitest"

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
})

beforeEach(() => {
  localStorage.clear()
  document.documentElement.lang = "pt-BR"
  document.documentElement.dataset.motion = "reduce"
  window.__media = {
    "(prefers-reduced-motion: reduce)": true,
    "(min-width: 1024px)": true,
    "(max-width: 767px)": false,
  }
})
