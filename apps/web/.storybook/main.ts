/**
 * A configuração do Storybook, o catálogo dos componentes (seção 14.9).
 *
 * O framework `@storybook/react-vite` monta o Storybook sobre o Vite do
 * projeto, com os plugins e o apelido `@` de `vite.config.ts`. O addon de
 * acessibilidade roda o axe em cada história; a regra de falha está em
 * `preview.tsx`.
 *
 * Quem usa: `pnpm storybook` (porta 6006) e `pnpm build-storybook`, que a
 * CI roda no job `web` e grava em `storybook-static`.
 */
import type { StorybookConfig } from '@storybook/react-vite';

const config: StorybookConfig = {
  // Toda história de `src`: os `*.stories.tsx` ao lado de cada componente.
  "stories": [
    "../src/**/*.stories.@(js|jsx|mjs|ts|tsx)"
  ],
  "addons": [
    "@storybook/addon-a11y"
  ],
  "framework": "@storybook/react-vite"
};
export default config;