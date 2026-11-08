/**
 * O que envolve toda história do Storybook: os estilos, os provedores e um
 * roteador (seção 14.9).
 *
 * Usa `globals.css`, o `AppProviders` de `src/app/providers.tsx`, com o
 * cache do TanStack Query e o contexto de movimento, e um `MemoryRouter`,
 * para os componentes com `Link` acharem um roteador. Quem usa: o
 * Storybook, por `main.ts`.
 */
import type { Preview } from "@storybook/react-vite"
import { MemoryRouter } from "react-router"

import { AppProviders } from "../src/app/providers.tsx"
import "../src/styles/globals.css"

// A página das histórias não vem do `index.html`: ela recebe aqui a classe
// `dark` e a língua que o app põe no `html`.
if (typeof document !== "undefined") {
  document.documentElement.classList.add("dark")
  document.documentElement.lang = "pt-BR"
}

const preview: Preview = {
  decorators: [
    // `MemoryRouter` guarda a URL na memória: um `Link` clicado numa
    // história não muda o endereço da página do Storybook.
    (Story) => (
      <AppProviders>
        <MemoryRouter>
          <div className="bg-background p-6 text-foreground">
            <Story />
          </div>
        </MemoryRouter>
      </AppProviders>
    ),
  ],
  parameters: {
    // Com `error`, o addon marca a história com violação do axe como
    // falha, e não como aviso. Ele só reprova uma execução quando as
    // histórias rodam como teste, pelo Vitest do Storybook, que o projeto
    // não instala. A CI só faz o build, então nenhuma violação a reprova;
    // a seção 14.9 diz que o addon roda na CI.
    a11y: {
      test: "error",
    },
    // Os controles de cor e de data para as props com esses nomes.
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
  },
}

export default preview
