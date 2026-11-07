import { resolve } from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"

import { preloadRoutes } from "./route-preload.ts"
import { securityHeaders } from "./security-headers.ts"

const TEST_EXCLUDE = [
  "**/node_modules/**",
  "**/dist/**",
  "**/cypress/**",
  "**/.{idea,git,cache,output,temp}/**",
  "**/{karma,rollup,webpack,vite,vitest,jest,ava,babel,nyc,cypress,tsup,build,eslint,prettier}.config.*",
  "e2e/**",
  "playwright.config.ts",
]

// Testes que não usam DOM rodam em Node, sem jsdom e sem o setup das telas. O das regras do
// ESLint carrega o ESLint inteiro; no jsdom, ele disputava a CPU com as telas (Etapa 11.1).
const NODE_TESTS = ["src/eslint/**/*.test.ts", "src/deploy/**/*.test.ts"]

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
    css: false,
    projects: [
      {
        extends: true,
        test: {
          name: "dom",
          environment: "jsdom",
          setupFiles: ["./src/test/setup.ts"],
          exclude: [...TEST_EXCLUDE, ...NODE_TESTS],
        },
      },
      {
        extends: true,
        test: {
          name: "node",
          environment: "node",
          include: NODE_TESTS,
          exclude: TEST_EXCLUDE,
        },
      },
    ],
  },
})
