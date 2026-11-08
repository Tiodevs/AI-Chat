# .storybook

A configuração do Storybook, o catálogo dos componentes de `src/components/ui` e `src/components/patterns`, com o addon de acessibilidade. Seção 14.9 do SDD.

## Arquivos

| Arquivo | O que faz | Quem usa |
|---|---|---|
| [main.ts](main.ts) | Onde estão as histórias (todo `*.stories.tsx` de `src`), o addon `@storybook/addon-a11y` e o framework `@storybook/react-vite`, que reaproveita o Vite do projeto | `pnpm storybook` e `pnpm build-storybook` |
| [preview.tsx](preview.tsx) | O que envolve cada história: `globals.css`, a classe `dark` e a língua no `html`, o `AppProviders` e um `MemoryRouter`. Liga `a11y.test: "error"` e os controles de cor e de data | O Storybook, por `main.ts` |

## Como ler

1. [main.ts](main.ts).
2. [preview.tsx](preview.tsx).
3. Uma história de cada pasta, como [button.stories.tsx](../src/components/ui/button.stories.tsx) e [assistant-message.stories.tsx](../src/components/patterns/assistant-message.stories.tsx).

São 54 arquivos de história: 23 em `components/ui` e 31 em `components/patterns`. Só o `sidebar-body.tsx`, a parte interna da barra lateral, não tem um; ele aparece nas histórias do `AppSidebar`.

Conceitos que ajudam:

- **Histórias e estados.** Cada `*.stories.tsx` exporta uma ou mais histórias, e a maioria tem uma só, `Estados`, que mostra lado a lado os estados do componente da seção 14.7, como foco, desabilitado, inválido e carregando.
- **O mesmo Vite.** O `@storybook/react-vite` monta o catálogo com os plugins e o apelido `@` de [vite.config.ts](../vite.config.ts). Por isso o plugin `route-preload.ts` ignora o HTML do Storybook.
- **Os provedores do app.** As histórias rodam dentro do `AppProviders`, como o app: um componente que lê `useMotion` ou o cache funciona igual. O `localStorage` e o movimento reduzido são os do navegador de quem abre o catálogo.
- **O addon de acessibilidade.** Ele roda o axe em cada história e mostra o resultado no painel. Com `a11y.test: "error"`, uma violação conta como falha, e não como aviso, quando as histórias rodam como teste, pelo Vitest do Storybook.

Divergência conhecida: a seção 14.9 diz que o addon roda na CI e falha com violação séria ou crítica. A CI só faz `pnpm build-storybook`, que não roda as histórias, e o projeto não instala o Vitest do Storybook; nenhuma violação nas histórias reprova a CI hoje. Além disso, o `test: "error"` conta qualquer violação, e não só as sérias e críticas. O axe das telas roda nos testes de tela e na e2e.

## Testes

- O job `web` do `ci.yml` roda `pnpm build-storybook`: uma história que não compila reprova a CI.
- O axe das telas montadas está nos testes de tela de `features` e na e2e ([README de src/test](../src/test/README.md) e [README de e2e](../e2e/README.md)).

Para abrir o catálogo, em `apps/web`: `pnpm storybook`, em `http://localhost:6006`. Ele não precisa da API.

## Leia também

- [SDD 14.6, inventário de componentes](../../../docs/sdd/experiencia.md#146-inventário-de-componentes)
- [SDD 14.7, estados de interação](../../../docs/sdd/experiencia.md#147-estados-de-interação)
- [SDD 14.9, governança](../../../docs/sdd/experiencia.md#149-governança)
- [Componentes ui](../src/components/ui/README.md) e [patterns](../src/components/patterns/README.md)
- [Guia, parte 12: design system e movimento](../../../docs/guia/12-design-system-e-movimento.md) e [parte 2: rodar e explorar](../../../docs/guia/02-rodar-e-explorar.md)
