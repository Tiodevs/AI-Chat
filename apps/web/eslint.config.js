/**
 * A configuração do ESLint do frontend, no formato plano (flat config).
 *
 * Além das regras recomendadas, ela guarda a fronteira de camadas do
 * frontend (seção 6.2 e NFR-1): componente não chama `fetch`, e só os
 * hooks de feature importam o cliente da API. O teste
 * `src/eslint/restrictions.test.ts` confere essa fronteira.
 *
 * Quem usa: `pnpm exec eslint .` (`pnpm lint`) e o job `web` do `ci.yml`.
 * A linha seguinte, em inglês, aponta a documentação do
 * `eslint-plugin-storybook`.
 */
// For more info, see https://github.com/storybookjs/eslint-plugin-storybook#configuration-flat-config-format
import storybook from "eslint-plugin-storybook";

import js from "@eslint/js"
import globals from "globals"
import reactHooks from "eslint-plugin-react-hooks"
import reactRefresh from "eslint-plugin-react-refresh"
import tseslint from "typescript-eslint"
import { defineConfig, globalIgnores } from "eslint/config"

// As mensagens que o ESLint mostra quando a fronteira é quebrada.
const fetchMessage =
  "Componentes não chamam fetch. O pedido fica num hook de feature (SDD 6.2)."

const apiImportMessage =
  "O cliente em src/lib/api só é importado por hooks de feature (SDD 6.2)."

const dangerMessage =
  "O atendimento mostra texto puro: sem dangerouslySetInnerHTML (SDD 29.8)."

// Os blocos valem na ordem, e um bloco posterior sobrepõe as regras de um
// anterior nos arquivos que ele cobre. As pastas de build ficam de fora.
export default defineConfig([globalIgnores(["dist", "storybook-static", "coverage", "node_modules"]), {
  // Todo `.ts` e `.tsx`: o código do app, os testes, a e2e e a
  // configuração da raiz.
  files: ["**/*.{ts,tsx}"],
  extends: [
    js.configs.recommended,
    tseslint.configs.recommended,
    reactHooks.configs.flat.recommended,
    reactRefresh.configs.vite,
  ],
  languageOptions: {
    globals: globals.browser,
  },
  rules: {
    // A regra protege a recarga rápida, que só funciona em arquivo que
    // exporta só componentes. Vários `.tsx` exportam também funções e
    // constantes, como `page-heading.tsx` e `router.tsx`.
    "react-refresh/only-export-components": "off",
    // Proíbe `fetch(...)` e `algo.fetch(...)`. Fora de `src/lib`, nenhum
    // arquivo chama a rede direto.
    "no-restricted-syntax": [
      "error",
      {
        selector:
          "CallExpression[callee.name='fetch'], CallExpression[callee.property.name='fetch']",
        message: fetchMessage,
      },
    ],
    // Proíbe importar `src/lib/api`, pelo apelido `@` ou por caminho
    // relativo.
    "no-restricted-imports": [
      "error",
      {
        patterns: [
          {
            group: [
              "@/lib/api",
              "@/lib/api/**",
              "**/lib/api",
              "**/lib/api/**",
            ],
            message: apiImportMessage,
          },
        ],
      },
    ],
  },
}, {
  // `src/lib` é a camada de transporte: chama `fetch` (`sse.ts`) e monta o
  // cliente (`lib/api`).
  files: ["src/lib/**/*.{ts,tsx}"],
  rules: {
    "no-restricted-syntax": "off",
    "no-restricted-imports": "off",
  },
}, {
  // Os hooks de feature (`use*.ts`) importam o cliente, mas continuam sem
  // `fetch` direto.
  files: ["src/features/**/use*.ts", "src/features/**/use*.tsx"],
  rules: {
    "no-restricted-imports": "off",
  },
}, {
  // O atendimento humano mostra texto livre de visitante e de equipe: nada de
  // HTML cru nessas pastas (seção 29.8). O bloco repete a regra do `fetch`,
  // porque um `no-restricted-syntax` posterior troca a lista inteira.
  files: [
    "src/features/ask/**/*.tsx",
    "src/features/attendance/**/*.tsx",
    "src/components/patterns/handoff-*.tsx",
    "src/components/patterns/attendant-message.tsx",
    "src/components/patterns/queue-list.tsx",
    "src/components/patterns/redact-dialog.tsx",
  ],
  rules: {
    "no-restricted-syntax": [
      "error",
      {
        selector:
          "CallExpression[callee.name='fetch'], CallExpression[callee.property.name='fetch']",
        message: fetchMessage,
      },
      {
        selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']",
        message: dangerMessage,
      },
    ],
  },
}, ...storybook.configs["flat/recommended"]])
