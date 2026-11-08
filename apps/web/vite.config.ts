/**
 * A configuração do Vite e do Vitest do frontend (seções 13.1, 13.4 e
 * 21.1).
 *
 * O Vite serve o app em desenvolvimento (`pnpm dev`), gera o build de
 * produção em `dist` (`pnpm build`) e serve esse build localmente
 * (`vite preview`). O Vitest lê o mesmo arquivo, pelo bloco `test`.
 *
 * Quem usa: os scripts do `package.json`, o Playwright (`webServer` dos
 * dois arquivos de configuração), o Storybook, que monta o Vite com estes
 * plugins, e a Vercel, que roda `pnpm build`. Usa `route-preload.ts` e
 * `security-headers.ts`.
 */
import { resolve } from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"

import { preloadRoutes } from "./route-preload.ts"
import { securityHeaders } from "./security-headers.ts"

// Definir `exclude` troca a lista padrão do Vitest, que por isso vem
// repetida nas cinco primeiras linhas. As duas últimas tiram os arquivos do
// Playwright: os `*.spec.ts` de `e2e` casariam com o padrão do Vitest.
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
    // JSX e recarga rápida dos componentes em desenvolvimento.
    react(),
    // O Tailwind 4 lê `src/styles/globals.css` e gera as classes usadas.
    tailwindcss(),
    // As rotas que abrem `/` vêm na primeira leva do navegador (seção 5.3, LCP).
    preloadRoutes(["src/app/shell.tsx", "src/app/route-frame.tsx", "src/app/routes/home.tsx"]),
  ],
  resolve: {
    // O mesmo `@` de `tsconfig.json`: `@/app/router.tsx` vira
    // `src/app/router.tsx`.
    alias: {
      "@": resolve(import.meta.dirname, "./src"),
    },
  },
  // Local, o navegador fala só com o Vite, na mesma origem, como faria com
  // a Vercel (seção 13.4). O proxy leva `/backend/v1/me` à API como
  // `/v1/me`, sem o segredo da borda: em `local` e `test`, a API não o
  // exige (seção 10.3). `changeOrigin` troca só o `Host`. O `Origin` do
  // navegador passa intacto, e a API o compara com `WEB_ORIGIN` nos pedidos
  // que mudam estado: abra o app no mesmo endereço de `WEB_ORIGIN`, como
  // `http://localhost:5173`. `API_PROXY_TARGET` aponta outra API, como a do
  // `docker-compose.yml` ou a da e2e.
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
    // Os testes não processam CSS: cada estilo importado vira um vazio.
    css: false,
    // Dois projetos, cada um com o seu ambiente. `extends: true` herda o
    // resto deste arquivo, como os plugins e o `@`.
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
