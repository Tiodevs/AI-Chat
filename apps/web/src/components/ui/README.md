# ui

Os componentes base do design system: os do shadcn/ui (estilo `radix-nova`), copiados para o projeto e ajustados aos tokens, aos alvos de toque e ao movimento do Atrium. São a camada de View mais baixa do frontend ([SDD 13.2](../../../../../docs/sdd/experiencia.md#132-mvc-no-frontend)) e a lista de base da [seção 14.6](../../../../../docs/sdd/experiencia.md#146-inventário-de-componentes).

## Arquivos

| Arquivo | O que faz | Quem usa | História |
|---|---|---|---|
| [alert-dialog.tsx](alert-dialog.tsx) | Confirmação de ação sem volta sobre o `AlertDialog` do Radix: não fecha com clique fora e abre com o foco em Cancelar. A ação é `destructive` por padrão | Excluir minha conta (`/account`) e Arquivar (`/admin/documents`) | [UI/AlertDialog](alert-dialog.stories.tsx) |
| [badge.tsx](badge.tsx) | Selo curto por `cva`. O projeto acrescentou as variantes de status `info`, `success`, `warning` e `danger` | Status de documentos, desfecho e avaliação em `/admin/quality`, status em `/admin/privacy`, `DueDateBadge` | [UI/Badge](badge.stories.tsx) |
| [button.tsx](button.tsx) | Botão por `cva` (`variant` e `size`), com `asChild` para vestir um link. 44 px no celular e o contorno de foco global | Todas as telas e quase todos os `patterns` | [UI/Button](button.stories.tsx) |
| [card.tsx](card.tsx) | Superfície de card e as partes dela: cabeçalho, título, descrição, ação, conteúdo e rodapé | Cartões de `/admin`, envio de documento, `SidebarNoticeCard`, `/sign-in` | [UI/Card](card.stories.tsx) |
| [chart.tsx](chart.tsx) | Moldura do Recharts: `ChartContainer` com o `ResponsiveContainer` e as cores das séries por `ChartConfig` | `TrendChartCard` e `GroupedBarCard` em `/admin` | [UI/Chart](chart.stories.tsx) |
| [checkbox.tsx](checkbox.tsx) | Caixa de seleção sobre o `Checkbox` do Radix, com 24 px e os tokens de controle | `ConsentFieldSet` (`/register` e `/register/form`) | [UI/Checkbox](checkbox.stories.tsx) |
| [dialog.tsx](dialog.tsx) | Diálogo modal sobre o `Dialog` do Radix, com o botão de fechar de 44 px | `SearchDialog` (busca do `⌘K`) | [UI/Dialog](dialog.stories.tsx) |
| [dropdown-menu.tsx](dropdown-menu.tsx) | Menu suspenso sobre o `DropdownMenu` do Radix, com itens, grupos de rádio e submenus | `ProfileButton` | [UI/DropdownMenu](dropdown-menu.stories.tsx) |
| [field.tsx](field.tsx) | Peças de formulário: `FieldSet`, `FieldGroup`, `Field` (orientação por `cva`), rótulo, descrição e `FieldError` com `role="alert"` | `Composer`, `PasswordCard`, `ConsentFieldSet`, `ProfileSummaryCard` e os formulários de entrar, cadastro, conta, privacidade e admin | [UI/Field](field.stories.tsx) |
| [input.tsx](input.tsx) | Campo de uma linha, com 44 px no celular e a borda `--border-strong` | Entrar, cadastro por formulário, conta, privacidade, documentos, `PasswordCard`, `ProfileSummaryCard`, `SearchDialog` | [UI/Input](input.stories.tsx) |
| [label.tsx](label.tsx) | Rótulo sobre o `Label` do Radix, sem mudança | `FieldLabel` e `ConsentFieldSet` | [UI/Label](label.stories.tsx) |
| [progress.tsx](progress.tsx) | Barra de progresso sobre o `Progress` do Radix, que recua com `translateX` | Orçamento diário de tokens em `/admin` | [UI/Progress](progress.stories.tsx) |
| [select.tsx](select.tsx) | Lista de opções sobre o `Select` do Radix. Só o alvo de 44 px mudou | Filtro de desfecho em `/admin/quality` | [UI/Select](select.stories.tsx) |
| [separator.tsx](separator.tsx) | Divisor sobre o `Separator` do Radix, decorativo por padrão | `SidebarBody` e `FieldSeparator` | [UI/Separator](separator.stories.tsx) |
| [sheet.tsx](sheet.tsx) | Painel lateral sobre o `Dialog` do Radix, preso a uma borda da tela | `MobileSidebar`, substituir documento, inspetor de conversa e pedido de titular | [UI/Sheet](sheet.stories.tsx) |
| [skeleton.tsx](skeleton.tsx) | Bloco de espera que pulsa, escondido do leitor de tela | `AssistantMessage`, `DataTable`, `StatCard` e as telas de conversa, cadastro, conta e admin | [UI/Skeleton](skeleton.stories.tsx) |
| [spinner.tsx](spinner.tsx) | Ícone que gira. Decorativo com `aria-hidden`; sem ele, `role="status"` com o nome "Carregando" | Botões de envio de todas as telas e o selo de processamento em `/admin/documents` | [UI/Spinner](spinner.stories.tsx) |
| [switch.tsx](switch.tsx) | Interruptor sobre o `Switch` do Radix, de 24 por 44 px | Consentimentos opcionais em `/account` | [UI/Switch](switch.stories.tsx) |
| [table.tsx](table.tsx) | Peças de `<table>` do shadcn, sem mudança, com rolagem horizontal | `DataTable` | [UI/Table](table.stories.tsx) |
| [tabs.tsx](tabs.tsx) | Abas sobre o `Tabs` do Radix, em pílula | Abas de `/account` e `SegmentedStatusCard` | [UI/Tabs](tabs.stories.tsx) |
| [textarea.tsx](textarea.tsx) | Campo de várias linhas, que cresce com o texto. Sem anel de foco (veja os comentários) | `Composer`, cadastro por conversa, canal do titular, nota em `/admin/privacy`, motivo em `/admin/quality` | [UI/Textarea](textarea.stories.tsx) |
| [toggle-group.tsx](toggle-group.tsx) | Chips de escolha sobre o `ToggleGroup` do Radix | Sugestões do início, períodos e filtros do admin, preferência de movimento, campos de escolha da conta e do cadastro, `ProfileSummaryCard`, `TrendChartCard` | [UI/ToggleGroup](toggle-group.stories.tsx) |
| [tooltip.tsx](tooltip.tsx) | Dica flutuante sobre o `Tooltip` do Radix. Exige um `TooltipProvider` acima | `SidebarBody`, na barra recolhida | [UI/Tooltip](tooltip.stories.tsx) |

## Como ler

Comece pelo [button.tsx](button.tsx): ele tem quase todos os conceitos da pasta. Depois leia [badge.tsx](badge.tsx), que mostra variantes acrescentadas pelo projeto; [field.tsx](field.tsx), [input.tsx](input.tsx) e [textarea.tsx](textarea.tsx), que montam um formulário; [checkbox.tsx](checkbox.tsx), [switch.tsx](switch.tsx), [tabs.tsx](tabs.tsx) e [toggle-group.tsx](toggle-group.tsx), que leem o `data-state` do Radix; e por fim [dialog.tsx](dialog.tsx), [sheet.tsx](sheet.tsx), [dropdown-menu.tsx](dropdown-menu.tsx) e [chart.tsx](chart.tsx). O cabeçalho de cada arquivo diz o que o projeto mudou no gerado pelo shadcn.

Conceitos que ajudam:

- **`ui` e `patterns`.** Aqui ficam as peças genéricas, sem regra do produto. A pasta [`patterns`](../patterns/README.md) compõe estas peças com as regras do Atrium. Nenhuma das duas chama a API: o ESLint barra `fetch` e o cliente `@/lib/api` nos componentes ([SDD 13.2](../../../../../docs/sdd/experiencia.md#132-mvc-no-frontend)).
- **shadcn/ui.** Não é uma biblioteca instalada: o CLI copia o código para esta pasta, e o projeto o edita ([ADR-010](../../../../../docs/adr/010-shadcn-ui.md)). Por isso cada arquivo pode divergir do modelo.
- **Radix.** O pacote `radix-ui` dá os primitivos (`Dialog`, `Checkbox`, `Tabs`...) com os papéis ARIA, o foco e o teclado prontos. O estado aparece como atributo no elemento (`data-state="checked"`, `"open"`, `"active"`, `"on"`), e as classes o leem com `data-[state=checked]:` ou com as variantes `data-open:`, `data-closed:`, `data-horizontal:` e `data-vertical:`, que vêm do `shadcn/tailwind.css` importado em [globals.css](../../styles/globals.css).
- **`cva` e `cn`.** O `cva` (class-variance-authority) monta a classe a partir da base e das variantes; o `VariantProps` tira daí o tipo das props. O `cn`, do pacote `cn`, junta classes condicionais e resolve conflitos do Tailwind com a última vencendo, então a `className` de quem chama vence a da variante.
- **`asChild` e `Slot`.** Com `asChild`, o componente não cria o próprio elemento: o `Slot` do Radix funde as props e a classe no filho, como um `Link`.
- **`ref` como prop.** No React 19, `ref` é uma prop comum, e os componentes são funções simples, sem `forwardRef`.
- **`data-slot`.** Cada peça marca o próprio nome (`data-slot="card-footer"`). Os pais usam isso em seletores como `has-data-[slot=card-footer]:`, e os testes também, como `[data-slot=badge]`.
- **Dos tokens às classes.** [tokens.css](../../styles/tokens.css) define as variáveis da [seção 14.2](../../../../../docs/sdd/experiencia.md#142-tokens-de-cor) (`--card`, `--primary`...) e os apelidos que o shadcn espera (`--destructive` é `--danger`, `--input` é `--border-strong`, `--accent` é `--muted`). [globals.css](../../styles/globals.css) registra cada uma em `@theme inline` (`--color-card: var(--card)`), e o Tailwind gera `bg-card` com `background-color: var(--card)`. O mesmo arquivo cria `rounded-card` (16 px), `rounded-nav` (10 px), `shadow-overlay` e as tipografias `text-caption` a `text-display` da [seção 14.3](../../../../../docs/sdd/experiencia.md#143-tipografia).
- **Só tema escuro.** O `index.html` põe `class="dark"` na raiz, então as classes `dark:` do shadcn valem sempre ([seção 14.8](../../../../../docs/sdd/experiencia.md#148-regras-de-uso)).
- **Foco.** `globals.css` desenha o contorno de 2 px em `--ring`, com 2 px de afastamento, em todo `:focus-visible` ([seção 14.7](../../../../../docs/sdd/experiencia.md#147-estados-de-interação)). Uma classe `outline-none` vence essa regra, porque a camada `utilities` do Tailwind vem depois da `base`. Por isso o projeto tirou o `outline-none` da maioria dos componentes; o `Select` e o `Textarea` ainda o têm.
- **Alvos de toque.** `max-md:min-h-11` dá 44 px abaixo de 768 px, e `md:min-h-8`, 32 px no desktop ([seção 15.8](../../../../../docs/sdd/experiencia.md#158-acessibilidade)).
- **Movimento.** Os componentes desta pasta não chamam o GSAP. Quem anima diálogos, sheets e menus é o padrão que os usa, com `forceMount` e o `useGsapPresence` de [`motion`](../../motion/README.md) (M14 da [seção 16.3](../../../../../docs/sdd/experiencia.md#163-catálogo)). As animações de CSS que restaram são o pulso do `Skeleton`, o giro do `Spinner`, a transição do `Progress` e as do `Select`; os estilos globais as cortam com movimento reduzido.

## Testes

- **Histórias do Storybook.** Cada componente tem um `*.stories.tsx` ao lado, com os estados da [seção 14.7](../../../../../docs/sdd/experiencia.md#147-estados-de-interação): repouso, foco, desabilitado, inválido e carregando, quando se aplicam. Rode `pnpm storybook` em `apps/web` e abra o painel Accessibility, do addon de acessibilidade configurado em [.storybook](../../../.storybook/README.md). O `preview.tsx` põe `a11y.test` em `"error"`, mas a CI só faz `pnpm build-storybook`: ela não executa as checagens do addon.
- **[raw-color.test.ts](../../styles/raw-color.test.ts).** Lê todo `.ts`, `.tsx` e `.css` de `src`, inclusive os comentários, e falha com cor em hexadecimal, classe de paleta do Tailwind ou função de cor fora de `tokens.css`.
- **[restrictions.test.ts](../../eslint/restrictions.test.ts).** Confere que o ESLint barra o cliente da API num arquivo de `components/ui`.
- Não há teste de unidade só desta pasta. Os componentes são exercitados pelos testes das telas em `src/features` e pelo axe das jornadas do Playwright ([e2e](../../../e2e/README.md)).

## Leia também

- SDD: [14.1 Referência e princípios](../../../../../docs/sdd/experiencia.md#141-referência-e-princípios), [14.2 Tokens de cor](../../../../../docs/sdd/experiencia.md#142-tokens-de-cor), [14.4 Espaço, forma e elevação](../../../../../docs/sdd/experiencia.md#144-espaço-forma-e-elevação), [14.6 Inventário de componentes](../../../../../docs/sdd/experiencia.md#146-inventário-de-componentes), [14.7 Estados de interação](../../../../../docs/sdd/experiencia.md#147-estados-de-interação), [14.8 Regras de uso](../../../../../docs/sdd/experiencia.md#148-regras-de-uso), [14.9 Governança](../../../../../docs/sdd/experiencia.md#149-governança), [15.8 Acessibilidade](../../../../../docs/sdd/experiencia.md#158-acessibilidade) e [16.3 Catálogo](../../../../../docs/sdd/experiencia.md#163-catálogo).
- ADRs: [010, shadcn/ui sobre Radix](../../../../../docs/adr/010-shadcn-ui.md) e [011, GSAP](../../../../../docs/adr/011-gsap.md).
- Guia: [parte 12, design system e movimento](../../../../../docs/guia/12-design-system-e-movimento.md).
- Pastas vizinhas: [patterns](../patterns/README.md), [styles](../../styles/README.md) e [motion](../../motion/README.md).
