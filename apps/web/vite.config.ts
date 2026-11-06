import { resolve } from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"

import { preloadRoutes } from "./route-preload.ts"
import { securityHeaders } from "./security-headers.ts"

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    // As rotas que abrem `/` vêm na primeira leva do navegador (seção 5.3, LCP).
    preloadRoutes(["src/app/shell.tsx", "src/app/route-frame.tsx", "src/app/routes/home.tsx"]),
  ],
  resolve: {
    alias: {
      "@": resolve(import.meta.dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/backend": {
        target: process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/backend/, ""),
      },
    },
  },
  // O preview usa o mesmo proxy do dev e os cabeçalhos de produção da seção 13.4.
  preview: {
    headers: securityHeaders,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    exclude: [
      "**/node_modules/**",
      "**/dist/**",
      "**/cypress/**",
      "**/.{idea,git,cache,output,temp}/**",
      "**/{karma,rollup,webpack,vite,vitest,jest,ava,babel,nyc,cypress,tsup,build,eslint,prettier}.config.*",
      "e2e/**",
      "playwright.config.ts",
    ],
  },
})
