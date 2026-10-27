import createClient from "openapi-fetch"

import type { paths } from "./schema.ts"

function apiBaseUrl(): string {
  if (typeof window === "undefined" || window.location.origin === "null") {
    return "http://127.0.0.1/backend"
  }
  return `${window.location.origin}/backend`
}

export const api = createClient<paths>({
  baseUrl: apiBaseUrl(),
  credentials: "include",
  fetch: (request) => globalThis.fetch(request),
})
