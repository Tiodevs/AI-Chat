// For more info, see https://github.com/storybookjs/eslint-plugin-storybook#configuration-flat-config-format
import storybook from "eslint-plugin-storybook";

import js from "@eslint/js"
import globals from "globals"
import reactHooks from "eslint-plugin-react-hooks"
import reactRefresh from "eslint-plugin-react-refresh"
import tseslint from "typescript-eslint"
import { defineConfig, globalIgnores } from "eslint/config"

const fetchMessage =
  "Componentes não chamam fetch. O pedido fica num hook de feature (SDD 6.2)."

const apiImportMessage =
  "O cliente em src/lib/api só é importado por hooks de feature (SDD 6.2)."

export default defineConfig([globalIgnores(["dist", "storybook-static", "coverage", "node_modules"]), {
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
    "react-refresh/only-export-components": "off",
    "no-restricted-syntax": [
      "error",
      {
        selector:
          "CallExpression[callee.name='fetch'], CallExpression[callee.property.name='fetch']",
        message: fetchMessage,
      },
    ],
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
  files: ["src/lib/**/*.{ts,tsx}"],
  rules: {
    "no-restricted-syntax": "off",
    "no-restricted-imports": "off",
  },
}, {
  files: ["src/features/**/use*.ts", "src/features/**/use*.tsx"],
  rules: {
    "no-restricted-imports": "off",
  },
}, ...storybook.configs["flat/recommended"]])
