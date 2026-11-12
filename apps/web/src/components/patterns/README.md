# patterns

Os componentes de produto do Atrium: compõem as peças de [`ui`](../ui/README.md) com as regras do produto, como o fio da conversa, os aceites do cadastro e os cartões do admin. São View ([SDD 13.2](../../../../../docs/sdd/experiencia.md#132-mvc-no-frontend)): recebem dados e callbacks das telas e não chamam a API. O inventário está na [seção 14.6](../../../../../docs/sdd/experiencia.md#146-inventário-de-componentes), e o movimento, na [seção 16.3](../../../../../docs/sdd/experiencia.md#163-catálogo).

## Arquivos

### Conversa

| Arquivo | O que faz | Quem usa | História |
|---|---|---|---|
| [chat-thread.tsx](chat-thread.tsx) | Lista de turnos da conversa, com a região `aria-live` que anuncia a resposta inteira no `done` | `/ask/:id?` (`features/ask/conversation-screen.tsx`) | [Patterns/ChatThread](chat-thread.stories.tsx) |
| [user-message.tsx](user-message.tsx) | Balão da pergunta, à direita, em `--card`. Na recusa médica, mostra a nota de privacidade no lugar do texto. M5 | `ChatThread` e a transcrição de `/register` | [Patterns/UserMessage](user-message.stories.tsx) |
| [assistant-message.tsx](assistant-message.tsx) | Resposta sem balão em todas as fases (espera, fluxo, concluída, interrompida, erro), com chips, fontes, badges e Útil, Não útil e Copiar. M6, M8 e M9 | `ChatThread` | [Patterns/AssistantMessage](assistant-message.stories.tsx) |
| [streaming-caret.tsx](streaming-caret.tsx) | Caret que pisca durante a geração, o único laço da interface. M7 | `AssistantMessage` e `AssistantBubble` | [Patterns/StreamingCaret](streaming-caret.stories.tsx) |
| [citation-chip.tsx](citation-chip.tsx) | Botão numerado no lugar de cada `[n]` do texto; leva o foco à fonte. Gancho da M8 | `AssistantMessage` | [Patterns/CitationChip](citation-chip.stories.tsx) |
| [source-list.tsx](source-list.tsx) | Lista recolhível das fontes, com título e seção, que o chip pode focar | `AssistantMessage` | [Patterns/SourceList](source-list.stories.tsx) |
| [outcome-badge.tsx](outcome-badge.tsx) | Selo do desfecho: respondida, abstenção, recusa médica, substituída e indisponível | `AssistantMessage` | [Patterns/OutcomeBadge](outcome-badge.stories.tsx) |
| [composer.tsx](composer.tsx) | Campo da pergunta que cresce, Enviar, Parar e o aviso de saúde. Enter envia, Shift+Enter quebra a linha. Rótulo, texto de exemplo, dica e limite trocam no atendimento humano | Início (`/`), conversa (`/ask/:id?`) e o console (`/attendance`) | [Patterns/Composer](composer.stories.tsx) |
| [attendant-message.tsx](attendant-message.tsx) | Mensagem da equipe no atendimento humano, à esquerda, com o rótulo "Equipe do Harborlight" e o ícone `Headset`, texto puro e o aviso no lugar da mensagem removida | O bloco do atendimento (`features/ask/handoff-block.tsx`) | [Patterns/AttendantMessage](attendant-message.stories.tsx) |
| [handoff-offer.tsx](handoff-offer.tsx) | A oferta do atendimento abaixo da resposta que não ajudou, ou o texto com a mesa telefônica quando ninguém pode atender | `/ask/:id` | [Patterns/HandoffOffer](handoff-offer.stories.tsx) |
| [handoff-dialog.tsx](handoff-dialog.tsx) | A confirmação com o texto da seção 29.9.5, antes de qualquer pedido à API | `/ask/:id` | [Patterns/HandoffDialog](handoff-dialog.stories.tsx) |
| [handoff-status-bar.tsx](handoff-status-bar.tsx) | A barra acima do compositor: posição na fila ou atendimento em curso, Reconectando e o botão de sair | `/ask/:id` | [Patterns/HandoffStatusBar](handoff-status-bar.stories.tsx) |
| [safety-notice.tsx](safety-notice.tsx) | Aviso fixo de que o Atrium é uma IA e não dá orientação médica | Início (`/`) | [Patterns/SafetyNotice](safety-notice.stories.tsx) |
| [request-id-copy.tsx](request-id-copy.tsx) | O `request_id` de um erro, em fonte mono, com o botão de copiar | Error boundary das rotas, erro da conversa, `ChatErrorNotice` e as falhas da conta, da privacidade, do cadastro e do admin | [Patterns/RequestIdCopy](request-id-copy.stories.tsx) |

### Cadastro

| Arquivo | O que faz | Quem usa | História |
|---|---|---|---|
| [assistant-bubble.tsx](assistant-bubble.tsx) | Fala do assistente com avatar e balão, e o estado "escrevendo" | `/register` | [Patterns/AssistantBubble](assistant-bubble.stories.tsx) |
| [chat-error-notice.tsx](chat-error-notice.tsx) | Aviso de falha na conversa guiada, com `request_id`, Tentar de novo, Fechar e ações extras | `/register` | [Patterns/ChatErrorNotice](chat-error-notice.stories.tsx) |
| [profile-summary-card.tsx](profile-summary-card.tsx) | O que a IA entendeu: cada campo com valor, Editar e "Por que pedimos". M10 | `/register` | [Patterns/ProfileSummaryCard](profile-summary-card.stories.tsx) |
| [password-card.tsx](password-card.tsx) | Passo da senha fora do chat, com medidor de força e a nota de que a IA não vê a senha. M12 | `/register` (no lugar do compositor) e `/register/form` | [Patterns/PasswordCard](password-card.stories.tsx) |
| [consent-field-set.tsx](consent-field-set.tsx) | Os dois aceites obrigatórios e os dois opcionais, com a personalização destacada | `/register` e `/register/form` | [Patterns/ConsentFieldSet](consent-field-set.stories.tsx) |
| [registration-stepper.tsx](registration-stepper.tsx) | Etapas Dados, Senha, Revisão e Aceite, com a barra de progresso. M11 | Nenhuma tela desde 2026-11-04; fica no Storybook | [Patterns/RegistrationStepper](registration-stepper.stories.tsx) |

### Admin

| Arquivo | O que faz | Quem usa | História |
|---|---|---|---|
| [stat-card.tsx](stat-card.tsx) | Indicador com legenda, número grande e variação; o valor final fica no `aria-label`. M2 | Linha de indicadores de `/admin` | [Patterns/StatCard](stat-card.stories.tsx) |
| [delta-badge.tsx](delta-badge.tsx) | Variação contra o período anterior, com ponto, seta e texto | `StatCard` | [Patterns/DeltaBadge](delta-badge.stories.tsx) |
| [stat-tile.tsx](stat-tile.tsx) | Bloco de contagem com ponto colorido e porcentagem | `SegmentedStatusCard` e as contagens de `/admin/privacy` | [Patterns/StatTile](stat-tile.stories.tsx) |
| [segmented-status-card.tsx](segmented-status-card.tsx) | Card com abas e barra segmentada, com as contagens em texto. M15 | "Desfechos" em `/admin` e o topo de `/admin/quality` | [Patterns/SegmentedStatusCard](segmented-status-card.stories.tsx) |
| [trend-chart-card.tsx](trend-chart-card.tsx) | Série no tempo com cursor, pílula de data, seletor de período e tabela equivalente. M3 e M4 | "Perguntas ao longo do tempo" em `/admin` | [Patterns/TrendChartCard](trend-chart-card.stories.tsx) |
| [grouped-bar-card.tsx](grouped-bar-card.tsx) | Barras agrupadas, duas séries por etapa, com tabela equivalente | "Funil de cadastro" em `/admin` | [Patterns/GroupedBarCard](grouped-bar-card.stories.tsx) |
| [data-table.tsx](data-table.tsx) | Tabela genérica por colunas, com carregando, vazia e cabeçalho de linha | `/admin/documents`, `/admin/quality` e `/admin/privacy` | [Patterns/DataTable](data-table.stories.tsx) |
| [file-dropzone.tsx](file-dropzone.tsx) | Área de envio com arrastar e soltar e o botão de escolher; exporta `formatFileSize` | Envio e substituição em `/admin/documents` | [Patterns/FileDropzone](file-dropzone.stories.tsx) |
| [due-date-badge.tsx](due-date-badge.tsx) | Prazo de pedido de titular em texto e data; exporta `dueState` e `formatDate` | Fila e sheet de `/admin/privacy` | [Patterns/DueDateBadge](due-date-badge.stories.tsx) |
| [pseudonym-badge.tsx](pseudonym-badge.tsx) | Tipo e pseudônimo de quem conversou, nunca o nome | Tabela e inspetor de `/admin/quality` | [Patterns/PseudonymBadge](pseudonym-badge.stories.tsx) |
| [tone.ts](tone.ts) | Tipo `Tone` e as classes de ponto e de fundo de cada tom de status | `DeltaBadge`, `StatTile` e `SegmentedStatusCard` | Sem história: não é componente |

### Casca

| Arquivo | O que faz | Quem usa | História |
|---|---|---|---|
| [app-sidebar.tsx](app-sidebar.tsx) | `AppSidebar`, a barra lateral recolhível do desktop e do tablet (M13), e `MobileSidebar`, a barra de 56 px com o menu num sheet (M14) | `app/shell.tsx`, com sessão, carregado sob demanda | [Patterns/AppSidebar](app-sidebar.stories.tsx) |
| [sidebar-body.tsx](sidebar-body.tsx) | Conteúdo da barra: logotipo, recolher, busca, grupos de navegação, aviso e perfil; põe o `TooltipProvider` | `AppSidebar` e `MobileSidebar` | Coberto pelas histórias do `AppSidebar` |
| [sidebar-notice-card.tsx](sidebar-notice-card.tsx) | Card "Novidades" com uma dica de privacidade e de uso | `SidebarBody` | [Patterns/SidebarNoticeCard](sidebar-notice-card.stories.tsx) |
| [profile-button.tsx](profile-button.tsx) | Nome de quem entrou e o menu com Conta, Sair e a preferência de movimento | `SidebarBody` | [Patterns/ProfileButton](profile-button.stories.tsx) |
| [guest-header.tsx](guest-header.tsx) | Cabeçalho sem sessão com Entrar, Criar conta e Cadastrar com IA; no celular, um disclosure de navegação | `app/shell.tsx`, sem sessão | [Patterns/GuestHeader](guest-header.stories.tsx) |
| [search-dialog.tsx](search-dialog.tsx) | Busca do `⌘K`: filtra as páginas da navegação pelo nome | `app/shell.tsx`, carregado sob demanda | [Patterns/SearchDialog](search-dialog.stories.tsx) |

### Console de atendimento

| Arquivo | O que faz | Quem usa | História |
|---|---|---|---|
| [presence-toggle.tsx](presence-toggle.tsx) | Disponível ou Ausente, num `ToggleGroup` de escolha única | `/attendance` | [Patterns/PresenceToggle](presence-toggle.stories.tsx) |
| [queue-list.tsx](queue-list.tsx) | A fila sem conteúdo: rótulo, espera, motivo da oferta, Devolvido, Visitante ausente e Assumir. Também `waitText` e `triggerText` | `/attendance` e `/admin/attendance` | [Patterns/QueueList](queue-list.stories.tsx) |
| [handoff-thread.tsx](handoff-thread.tsx) | A conversa com o Atrium e as mensagens do atendimento, em texto puro, com Remover conteúdo | `/attendance` e o `Sheet` de `/admin/attendance` | [Patterns/HandoffThread](handoff-thread.stories.tsx) |
| [redact-dialog.tsx](redact-dialog.tsx) | A remoção de conteúdo com a categoria num `ToggleGroup` de escolha única | `/attendance` | [Patterns/RedactDialog](redact-dialog.stories.tsx) |

## Como ler

Siga uma pergunta. Comece por [chat-thread.tsx](chat-thread.tsx), passe para [user-message.tsx](user-message.tsx) e [assistant-message.tsx](assistant-message.tsx), que puxa [citation-chip.tsx](citation-chip.tsx), [source-list.tsx](source-list.tsx), [outcome-badge.tsx](outcome-badge.tsx) e [streaming-caret.tsx](streaming-caret.tsx), e termine no [composer.tsx](composer.tsx). Depois leia o cadastro ([profile-summary-card.tsx](profile-summary-card.tsx), [password-card.tsx](password-card.tsx) e [consent-field-set.tsx](consent-field-set.tsx)), o admin a partir de [tone.ts](tone.ts) e [stat-card.tsx](stat-card.tsx), e a casca a partir de [app-sidebar.tsx](app-sidebar.tsx). O cabeçalho de cada arquivo lista os estados, a acessibilidade e o movimento.

Conceitos que ajudam:

- **`ui` e `patterns`.** As peças de `ui` não sabem nada do hospital. Aqui ficam as regras do produto: a nota de privacidade da recusa, os tons de cada desfecho, o destaque do consentimento sensível. Os dados chegam prontos das telas e dos modelos puros de `features` (os tipos de `features/ask/types.ts`, as funções de `features/registration/model.ts`); as ações sobem por callback. O ESLint barra `fetch` e o cliente da API nesta pasta.
- **Textos.** Os textos visíveis vêm de [`pt.ts`](../../i18n/pt.ts) ([seção 15.7](../../../../../docs/sdd/experiencia.md#157-diretrizes-de-texto)); os componentes não escrevem frases no código.
- **Movimento pelos presets.** Todo componente que anima chama um preset de [`motion/presets.ts`](../../motion/presets.ts) dentro de `useGSAP`, com o `scope` na ref do componente ([seção 16.5](../../../../../docs/sdd/experiencia.md#165-regras-de-implementação)). O `useGSAP` roda depois da montagem e desfaz as animações ao desmontar. O componente só passa o `reduced` do `useMotion()`; quem decide o que fazer com movimento reduzido é o preset ([seção 16.4](../../../../../docs/sdd/experiencia.md#164-movimento-reduzido)). Os atributos `data-*` são os ganchos que os presets procuram: `data-citation`, `data-outgoing` e `data-incoming`, `data-highlight` e `data-confirm`, `data-segment` e `data-scale`, `data-flip-id` e `data-sidebar-label`.
- **Onde está cada movimento.** M2 `StatCard`, M3 e M4 `TrendChartCard`, M5 `UserMessage`, M6 `AssistantMessage` (e o `AssistantBubble`), M7 `StreamingCaret`, M8 chips no `AssistantMessage`, M9 `AssistantMessage`, M10 `ProfileSummaryCard`, M11 `RegistrationStepper`, M12 `PasswordCard`, M13 `AppSidebar`, M14 `MobileSidebar`, `GuestMenu` e `SearchDialog`, M15 `SegmentedStatusCard`. A M1 fica na casca (`app/shell.tsx`), e a M16 tem o preset `press`, sem uso.
- **Acessibilidade.** Regiões `aria-live` anunciam o que muda sem foco (a resposta no `ChatThread`, o campo entendido no `ProfileSummaryCard`). Erros usam `role="alert"`, e nunca dependem só da cor: texto, ícone e borda dizem o mesmo ([seção 15.8](../../../../../docs/sdd/experiencia.md#158-acessibilidade)). Gráficos são `aria-hidden` e têm uma tabela equivalente em `sr-only`. Rótulos escondidos usam `sr-only`, nunca `visibility: hidden`. Alvos de 44 px no celular e 32 px no desktop.
- **Tokens de status.** A cor só marca status ([seção 14.1](../../../../../docs/sdd/experiencia.md#141-referência-e-princípios)). O fundo de um status é o par translúcido da [seção 14.2](../../../../../docs/sdd/experiencia.md#142-tokens-de-cor), `color-mix` do token com 15% de opacidade, escrito por inteiro nas classes (`tone.ts`, `OutcomeBadge`, os alertas).

## Testes

- **Histórias do Storybook.** Todo componente tem um `*.stories.tsx` ao lado, com os estados das seções [14.7](../../../../../docs/sdd/experiencia.md#147-estados-de-interação) e [15.5](../../../../../docs/sdd/experiencia.md#155-telas); o `SidebarBody` aparece nas do `AppSidebar`. Rode `pnpm storybook` em `apps/web` e use o painel Accessibility do addon configurado em [.storybook](../../../.storybook/README.md). A CI só faz o build do Storybook.
- **[assistant-message.test.tsx](assistant-message.test.tsx).** Uma citação agrupada, como `[2, 3]`, vira um chip por fonte, e um grupo com fonte desconhecida fica como texto.
- **Testes das telas que cobrem esta pasta:** [shell.test.tsx](../../app/shell.test.tsx) (cabeçalho do visitante, menu do celular, barra recolhida, perfil, Sair e preferência de movimento), [ask.test.tsx](../../features/ask/ask.test.tsx) (troca da resposta e a região ao vivo, que só recebe o texto no `done`), [registration.test.tsx](../../features/registration/registration.test.tsx) (resumo, foco na senha depois da M12, aceites e destaque), [insights.test.tsx](../../features/admin/insights.test.tsx) (indicadores com o valor no `aria-label` e tabelas dos gráficos), [privacy-queue.test.tsx](../../features/admin/privacy-queue.test.tsx) (`dueState` e o `data-due`) e [documents.test.tsx](../../features/admin/documents.test.tsx) (envio pelo `FileDropzone`).
- **Movimento:** [presets.test.ts](../../motion/presets.test.ts) confere cada preset com e sem movimento reduzido, e o Playwright roda J1 e J3 com movimento em `e2e/motion.spec.ts`.
- **[raw-color.test.ts](../../styles/raw-color.test.ts)** varre esta pasta, inclusive os comentários, atrás de cor crua.

## Leia também

- SDD: [13.2 MVC no frontend](../../../../../docs/sdd/experiencia.md#132-mvc-no-frontend), [14.5 Layout](../../../../../docs/sdd/experiencia.md#145-layout), [14.6 Inventário de componentes](../../../../../docs/sdd/experiencia.md#146-inventário-de-componentes), [14.7 Estados de interação](../../../../../docs/sdd/experiencia.md#147-estados-de-interação), [15.5 Telas](../../../../../docs/sdd/experiencia.md#155-telas), [15.6 Padrões de experiência com IA](../../../../../docs/sdd/experiencia.md#156-padrões-de-experiência-com-ia), [15.8 Acessibilidade](../../../../../docs/sdd/experiencia.md#158-acessibilidade), [16.3 Catálogo](../../../../../docs/sdd/experiencia.md#163-catálogo) e [16.4 Movimento reduzido](../../../../../docs/sdd/experiencia.md#164-movimento-reduzido).
- Plano: a [Etapa 14.3](../../../../../docs/plano-de-acao.md#etapa-143--foco-rolagem-e-leitor-de-tela) corrige o foco do compositor e das avaliações, a região live da conversa e a saída do `useGsapPresence`.
- Guia: [parte 12, design system e movimento](../../../../../docs/guia/12-design-system-e-movimento.md) e [parte 11, frontend por dentro](../../../../../docs/guia/11-frontend-por-dentro.md).
- Pastas vizinhas: [ui](../ui/README.md), [motion](../../motion/README.md), [features/ask](../../features/ask/README.md), [features/registration](../../features/registration/README.md) e [features/admin](../../features/admin/README.md).
