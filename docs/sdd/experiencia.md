# Frontend, design system, UX e movimento

Parte da [especificação do Atrium](../sdd.md). A numeração das seções é a do documento completo.

## 13. Arquitetura do frontend

### 13.1 Pilha

| Responsabilidade | Escolha |
|---|---|
| Linguagem e build | React 19, TypeScript estrito, Vite |
| Rotas | React Router em modo de dados, com rotas carregadas sob demanda |
| Estado do servidor | TanStack Query |
| Formulários | React Hook Form com Zod. O servidor continua sendo a autoridade. |
| Cliente da API | `openapi-fetch` com tipos gerados por `openapi-typescript` |
| Fluxo SSE | `fetch` com `ReadableStream` e um leitor próprio em `src/lib/sse.ts`. `EventSource` não serve porque o envio é `POST`. |
| Componentes | shadcn/ui sobre Radix UI, ícones Lucide |
| Estilo | Tailwind CSS com tokens em variáveis CSS |
| Gráficos | Recharts, carregado só nas rotas de admin |
| Tabelas | TanStack Table |
| Paleta de comandos | `cmdk`, pelo componente Command do shadcn/ui |
| Notificações | Sonner |
| Movimento | GSAP com `@gsap/react` e o plugin Flip |
| Fonte | Geist Sans e Geist Mono, servidas pela própria origem |
| Catálogo | Storybook com o addon de acessibilidade |

### 13.2 MVC no frontend

| Papel | Onde | Regra |
|---|---|---|
| Model | `src/lib/api` e o cache do TanStack Query | Única fonte de dados do servidor |
| Controller | Hooks de feature, como `useAskConversation`, e os loaders do React Router | Orquestram pedidos, fluxo, cancelamento e invalidação de cache |
| View | `components/ui`, `components/patterns` e as páginas em `features` | Recebem dados e callbacks. Não chamam a API. |

### 13.3 Rotas e guardas

Os loaders de rotas protegidas chamam `queryClient.ensureQueryData` para `GET /v1/me`. Um membro sem sessão vai para `/sign-in` com `returnTo`. Uma rota de admin com usuário comum mostra a página 403. Um membro com documento legal novo vai para a tela de novo aceite antes de continuar.

Cada rota tem um error boundary com a mensagem amigável e o `request_id` copiável.

### 13.4 Desenvolvimento local e produção

O `vite.config.ts` faz proxy de `/backend` para `http://127.0.0.1:8000` e remove o prefixo. Assim o desenvolvimento local também é de mesma origem.

Na Vercel, o `vercel.ts` define, nesta ordem:

```ts
import { routes, type VercelConfig } from "@vercel/config/v1";

export const config: VercelConfig = {
  framework: "vite",
  git: { deploymentEnabled: false },
  rewrites: [
    routes.rewrite("/backend/:path*", `${process.env.API_URL}/:path*`),
    routes.rewrite("/((?!backend/).*)", "/index.html"),
  ],
};
```

`API_URL` é lida no build, então cada ambiente da Vercel aponta para a sua API. A publicação por Git fica desligada porque o GitHub Actions publica, seção 22.

Cabeçalhos definidos na Vercel:

| Caminho | Cabeçalho |
|---|---|
| `/backend/*` | `x-vercel-enable-rewrite-caching: 0` |
| Todos | `Content-Security-Policy` com `default-src 'self'`, `connect-src 'self'`, `img-src 'self' data:`, `frame-ancestors 'none'` |
| Todos | `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` sem câmera, microfone e geolocalização |
| `/assets/*` | `Cache-Control: public, max-age=31536000, immutable` |
| `/index.html` | `Cache-Control: no-cache` |

## 14. Design system

### 14.1 Referência e princípios

A referência é a imagem do painel escuro enviada em 2026-10-25. A amostragem de pixels mostra que a paleta é a escala neutra do Tailwind, quase sem cor. O selo "Radix UI, Lucide" no canto da imagem indica a base de componentes e de ícones.

O que a referência ensina, e o Atrium adota:

- superfícies separadas por luminosidade, não por sombra
- bordas quase invisíveis
- números grandes com legenda pequena e cinza
- cor só para significado, como alta, queda, sucesso e erro
- navegação lateral agrupada por seção, com busca e atalho de teclado
- estado selecionado em branco sobre preto, como a data em destaque no gráfico

Princípios:

1. **Calma.** O hospital é um lugar de ansiedade. A interface é monocromática e silenciosa.
2. **A cor tem significado.** Verde, vermelho, âmbar e azul aparecem só como status.
3. **Confiança visível.** Fontes, avisos e desfechos têm componentes próprios.
4. **Acessível por padrão.** Todo par de cores de texto passa em WCAG AA.
5. **Um token para cada decisão.** Nenhuma cor crua no código de produto.

### 14.2 Tokens de cor

Os tokens primitivos ficam em `src/styles/tokens.css`. Os componentes usam só os semânticos.

| Token semântico | Valor | Uso | Origem na imagem |
|---|---|---|---|
| `--shell` | `#0A0A0A` | Barra lateral e moldura do app | Fundo da barra lateral |
| `--background` | `#101010` | Tela principal | Espaço entre os cards |
| `--card` | `#171717` | Cards, campo de busca, item ativo da navegação | Cards de indicador e de gráfico |
| `--popover` | `#262626` | Tooltip, menu, paleta de comandos | Tooltip do gráfico |
| `--muted` | `#1C1C1C` | Hover em superfícies | Derivado |
| `--border` | `#222222` | Borda de card e divisores | Borda sutil dos cards |
| `--border-strong` | `#333333` | Campos de formulário e controles | Derivado |
| `--foreground` | `#EDEDED` | Texto principal | Item ativo da navegação |
| `--foreground-strong` | `#FFFFFF` | Títulos e números grandes | Números dos indicadores |
| `--muted-foreground` | `#A3A3A3` | Rótulos e navegação inativa | Rótulos e itens inativos |
| `--subtle-foreground` | `#8F8F8F` | Legendas, eixos e textos auxiliares | Eixos do gráfico, ajustado |
| `--primary` | `#FAFAFA` | Botão primário, seleção invertida, aba ativa | Pílula da data e sublinhado da aba |
| `--primary-foreground` | `#0A0A0A` | Texto sobre `--primary` | Texto da pílula da data |
| `--ring` | `#A3A3A3` | Anel de foco | Derivado |
| `--success` | `#10B981` | Alta, resposta fundamentada, pronto | Indicador verde |
| `--danger` | `#F87171` | Queda, erro, recusa, exclusão | Indicador vermelho |
| `--warning` | `#FBBF24` | Abstenção, prazo próximo, orçamento perto do limite | Novo |
| `--info` | `#60A5FA` | Aviso neutro, processamento | Novo |
| `--chart-1` a `--chart-4` | `#E5E5E5`, `#A3A3A3`, `#525252`, `#404040` | Séries em tons de cinza | Barras e área do gráfico |
| `--chart-area` | gradiente de `rgb(255 255 255 / 0.16)` a `0` | Preenchimento da área | Área do gráfico de receita |

Status usam o par cor mais fundo translúcido: `color-mix(in oklab, var(--success) 15%, transparent)` atrás do texto ou do ponto, como os indicadores da imagem.

**Ajuste de contraste.** O cinza dos eixos da imagem fica perto de `#737373`, com 3,8:1 sobre `#171717`, abaixo do mínimo AA de 4,5:1 para texto pequeno. O token `--subtle-foreground` sobe para `#8F8F8F`, que dá cerca de 5,5:1 sobre `--card` e 4,7:1 sobre `--popover`. Um teste automático calcula o contraste de cada par texto e fundo declarado nos tokens e falha abaixo de 4,5:1.

### 14.3 Tipografia

Geist Sans para a interface e Geist Mono para ids, `request_id` e código. Números usam `font-variant-numeric: tabular-nums`, para indicadores e tabelas não pularem quando mudam.

| Token | Tamanho e entrelinha | Peso | Uso |
|---|---|---|---|
| `text-caption` | 12/16 | 400 | Eixos, legendas, metadados |
| `text-label` | 13/18 | 500 | Rótulos de card, grupos da navegação |
| `text-body` | 14/20 | 400 | Texto de interface |
| `text-message` | 15/24 | 400 | Mensagens do chat |
| `text-title` | 18/26 | 600 | Título de página, como "Dashboard" na imagem |
| `text-metric` | 28/34 | 600 | Número de indicador |
| `text-display` | 36/44 | 600 | Título da página inicial |

A entrelinha das mensagens é maior que a da interface porque respostas longas são lidas, não escaneadas.

### 14.4 Espaço, forma e elevação

- Grade de 4 px. Espaçamentos 4, 8, 12, 16, 20, 24, 32, 40 e 48.
- Padding de card: 20 px no desktop e 16 px no celular. Espaço entre cards: 12 px no celular e 16 px no desktop.
- Raios: 8 px em campos e botões, 10 px em itens de navegação, 16 px em cards e completo em pílulas e badges.
- Elevação: cards não têm sombra. Só tooltip, menu, diálogo e paleta de comandos têm `0 8px 24px rgb(0 0 0 / 0.5)`, com borda `--border`.
- Ícones Lucide: 16 px com traço 1,75 na navegação e nos botões, 14 px nos badges.

### 14.5 Layout

| Região | Desktop, 1024 px ou mais | Tablet, de 768 a 1023 px | Celular, abaixo de 768 px |
|---|---|---|---|
| Barra lateral | 240 px fixa, recolhível para 64 px só com ícones | Recolhida em 64 px | Sheet aberto pelo botão de menu |
| Conteúdo | Até 1280 px, padding 24 px | Padding 20 px | Padding 16 px |
| Chat | Coluna de até 760 px, centralizada | A mesma | Largura total, compositor fixo embaixo, com área segura |
| Cards de indicador | Quatro por linha | Dois por linha | Um por linha, rolagem vertical |

A barra lateral segue a imagem: logotipo e botão de recolher no topo, busca com `⌘K`, grupos rotulados, um card "What's new" acima do rodapé e o botão de perfil no rodapé.

### 14.6 Inventário de componentes

Componentes base do shadcn/ui: Button, Input, Textarea, Field, FieldGroup, FieldSet, Checkbox, Switch, RadioGroup, ToggleGroup, Select, Tabs, Card, Badge, Alert, AlertDialog, Dialog, Sheet, Popover, Tooltip, DropdownMenu, Command, Separator, Skeleton, Empty, Spinner, Progress, Table, Chart e Sonner.

Componentes de produto em `components/patterns`, mapeados a partir da imagem:

| Na imagem | No Atrium | Onde |
|---|---|---|
| Barra lateral com grupos Platform e System | `AppSidebar` com grupos Assistant e Account no visitante, Operations e System no admin | Todas as telas |
| Busca com `⌘K` | `CommandPalette` para navegar, abrir conversas e ações | Todas as telas |
| Cards Leads, Conversion Rate e CLV | `StatCard` com `DeltaBadge`, o ponto colorido e a variação | Visão geral do admin |
| Gráfico Revenue over time com cursor e tooltip | `TrendChartCard` com cursor vertical, tooltip e pílula de data invertida | Visão geral do admin |
| Leads Management com abas e barra segmentada | `SegmentedStatusCard` para status de ingestão e desfechos | Documentos e qualidade |
| Blocos Open e In Progress | `StatTile` para contagens, como Ready e Processing | Documentos e qualidade |
| Retention Rate com barras agrupadas | `GroupedBarCard` para o funil de cadastro, chat contra formulário | Visão geral do admin |
| Card What's new | `SidebarNoticeCard` com dicas de privacidade e de uso | Barra lateral do visitante |
| Botão Customizer no rodapé | `ProfileButton` com menu de conta | Barra lateral |
| Menu de três pontos | `CardActionsMenu` | Cards do admin |

Componentes sem equivalente na imagem:

| Componente | Função |
|---|---|
| `ChatThread` | Lista de mensagens com `aria-live` |
| `UserMessage` | Balão à direita em `--card` |
| `AssistantMessage` | Texto sem balão, citações e ações |
| `StreamingCaret` | Indica geração em andamento |
| `CitationChip` e `SourceList` | Marcadores numerados e lista de fontes com título e seção |
| `OutcomeBadge` | Answered, Not in sources, Medical advice declined, Replaced e Unavailable |
| `Composer` | Campo que cresce, enviar, parar e o aviso de saúde |
| `SafetyNotice` | Alert permanente sobre IA e orientação médica |
| `RegistrationStepper` | Details, Password, Review e Agree |
| `ProfileSummaryCard` | Campos entendidos pela IA, editáveis, com o motivo de cada pergunta |
| `PasswordCard` | Passo seguro, fora do chat, com medidor de força |
| `ConsentFieldSet` | Aceites obrigatórios e opcionais, com o consentimento sensível destacado |
| `FileDropzone` | Upload de documentos |
| `DataTable` | Tabelas do admin |
| `PseudonymBadge` | Identidade pseudonimizada com a ação de revelar |
| `DueDateBadge` | Prazo de pedido de titular |
| `RequestIdCopy` | Copia o `request_id` nas telas de erro |

### 14.7 Estados de interação

| Estado | Regra |
|---|---|
| Hover | Superfície sobe um degrau: `--card` vira `--muted` sobre o shell. Texto inativo vira `--foreground`. |
| Foco visível | Anel de 2 px em `--ring` com 2 px de afastamento. Nunca removido. |
| Ativo ou selecionado | Fundo `--card` na navegação. `--primary` com `--primary-foreground` em seleção forte. |
| Desabilitado | Opacidade 0,5 e cursor padrão. O motivo aparece num tooltip quando não é óbvio. |
| Inválido | Borda `--danger`, mensagem abaixo do campo, ícone. Nunca só a cor. |
| Carregando | Skeleton no formato do conteúdo. Spinner só dentro de botões. |

### 14.8 Regras de uso

- Use os componentes do shadcn/ui antes de criar marcação própria.
- Use os tokens semânticos, nunca cores cruas como `bg-neutral-900`.
- Formulários usam `FieldGroup` e `Field`, com `aria-invalid` no controle.
- Diálogos e sheets sempre têm título, mesmo que visualmente escondido.
- Layout com `flex` e `gap`. Sem `space-x` e `space-y`.
- Nada de texto em cinza abaixo de `--subtle-foreground`.
- O tema claro fica para depois. A versão 1 declara `color-scheme: dark`.

### 14.9 Governança

- O Storybook documenta cada componente de `components/ui` e `components/patterns`, com todos os estados da seção 14.7.
- O addon de acessibilidade do Storybook roda na CI e falha com violação séria ou crítica.
- Uma mudança de token exige atualizar a seção 14.2 na mesma mudança.

## 15. Plano de UI/UX

### 15.1 Princípios de experiência

1. **Resposta primeiro.** A caixa de pergunta fica acima da dobra na página inicial. Ninguém precisa de conta para perguntar.
2. **Mostre de onde vem.** Toda resposta de fato tem fontes clicáveis.
3. **Honestidade sobre limites.** Quando não sabe, o Atrium diz que não sabe e dá o telefone da mesa.
4. **Sem beco sem saída.** Toda tela de erro ou recusa oferece um próximo passo: tentar de novo, ligar ou usar o formulário.
5. **Privacidade no momento certo.** O motivo de cada dado aparece quando ele é pedido, não só num documento longo.
6. **A IA ajuda, a pessoa decide.** No cadastro, o visitante vê o que a IA entendeu, corrige e confirma antes de qualquer conta existir.
7. **Movimento explica, não decora.** Seção 16.

### 15.2 Personas

| Persona | Contexto | Necessidade | Implicação de desenho |
|---|---|---|---|
| Marta, 67 anos | Vai visitar o marido internado. Usa o celular, tem pouca familiaridade digital. | Horário de visita e onde estacionar, rápido | Alvos grandes, sugestões prontas, texto simples, nada de cadastro no caminho |
| Diego, 34 anos | Acompanha a mãe em exames. Quer guardar as informações. | Cadastro rápido e histórico | Cadastro por conversa, opcionais puláveis, formulário a um clique |
| Ana, operadora | Mantém o corpus e a qualidade | Ver o que falha e corrigir | Painel denso como a referência, filtros por desfecho, link direto para o rastro |

### 15.3 Jornadas

| ID | Jornada | Sucesso |
|---|---|---|
| J1 | Convidado pergunta o horário de visita no celular | Resposta com fonte em menos de 15 segundos, sem cadastro |
| J2 | Convidado descreve um sintoma | Recusa clara com orientação de emergência. A mensagem não fica guardada. |
| J3 | Cadastro por conversa com opcionais pulados | Conta criada com só os dados obrigatórios e os aceites |
| J4 | Troca para o formulário no meio do chat | Campos já entendidos vêm preenchidos. Nada é perdido. |
| J5 | Membro exporta os dados e exclui a conta | Arquivo baixado. Conta excluída depois de uma confirmação. |
| J6 | Admin substitui um documento e acompanha a ingestão | Versão nova ativa. A anterior continua respondendo até lá. |
| J7 | Admin investiga uma resposta marcada como não útil | Da visão de qualidade à conversa e ao rastro no LangSmith em até três cliques |
| J8 | Pessoa sem conta pede a eliminação de dados | Pedido aberto com prazo visível para o admin |

### 15.4 Arquitetura de informação

```text
Visitante
  /                     Início: pergunta, sugestões, aviso
  /ask/:id?             Conversa
  /register             Cadastro por conversa
  /register/form        Cadastro por formulário
  /sign-in              Entrar
  /account              Conta: Profile, Conversations, Privacy
  /privacy              Aviso de Privacidade e canal do titular
  /terms                Termos de Uso
  /legal/accept         Novo aceite após mudança de versão

Admin
  /admin                Visão geral
  /admin/documents      Documentos
  /admin/quality        Qualidade e conversas
  /admin/privacy        Pedidos de titular
```

A navegação do visitante tem os grupos **Assistant** (New question e Conversations, para membros) e **Account** (Register ou Sign in, Account e Privacy). A do admin tem **Operations** (Overview, Documents e Quality) e **System** (Privacy requests). A paleta `⌘K` lista as mesmas entradas e, para membros, as conversas recentes.

### 15.5 Telas

Cada tela descreve objetivo, composição e estados. Os textos citados são a cópia em inglês do produto.

#### Início `/`

- **Objetivo:** responder à primeira pergunta sem atrito.
- **Composição:** título em `text-display` "How can we help you at Harborlight?", `Composer` em destaque e quatro sugestões em `ToggleGroup` de chips: Visiting hours, Parking, Emergency entrance e Cafeteria hours. `SafetyNotice` abaixo. Links discretos para Register e Sign in.
- **Estados:** sem estado vazio, porque a tela já é o ponto de partida. Com o orçamento estourado, o compositor fica desabilitado com o telefone da mesa.

#### Conversa `/ask/:id?`

- **Objetivo:** ler a resposta e conferir a fonte.
- **Composição:** coluna central de até 760 px. `UserMessage` à direita. `AssistantMessage` à esquerda, sem balão, com `CitationChip` no texto e `SourceList` recolhível abaixo. Ações depois de `done`: útil, não útil e copiar. O compositor fica fixo embaixo, com o botão Stop durante a geração.

| Estado | O que a pessoa vê |
|---|---|
| Vazio | As sugestões do início |
| Aguardando o primeiro token | Três linhas de skeleton e o caret, com `aria-busy` |
| Em fluxo | O texto chegando e o caret, com o botão Stop |
| Respondido | Texto, fontes e ações de feedback |
| Abstenção | Badge "Not in our published information" e o telefone da mesa |
| Recusa médica | Alert com a orientação de emergência e a nota "For your privacy, we didn't keep this message." no lugar da mensagem |
| Substituída | O rascunho dá lugar à resposta segura, com a nota "I couldn't verify that answer, so I replaced it." |
| Interrompida | "Stopped." e o botão Retry |
| Limite de taxa | "You've asked a lot of questions. Try again in N minutes." |
| Indisponível | A resposta fixa de indisponibilidade |
| Erro | Mensagem amigável, Retry e `RequestIdCopy` |

#### Cadastro por conversa `/register`

- **Objetivo:** criar a conta conversando, sem perder o controle dos dados.
- **Composição no desktop:** `RegistrationStepper` no topo. À esquerda, o chat. À direita, o `ProfileSummaryCard`, que se preenche à medida que a IA entende os campos. Cada campo tem um link "Why we ask" e pode ser editado ali mesmo. No celular, o cartão vira uma faixa recolhível acima do chat.
- **Passo da senha:** o `PasswordCard` aparece no lugar do compositor, com a nota "Your password goes straight to our server. The AI never sees it."
- **Passo de revisão:** o resumo completo com Edit em cada linha e o botão Looks right.
- **Passo de aceite:** `ConsentFieldSet` com os dois aceites obrigatórios e os dois opcionais. O opcional de personalização fica destacado e explica que tipo de visitante e motivo da visita podem indicar que a pessoa é paciente. Os opcionais começam desmarcados.
- **Sempre visível:** o link "Use a form instead".
- **Estados:** campo com erro aparece no cartão e é pedido de novo no chat. E-mail já cadastrado oferece Sign in. Com o Gemini indisponível, a tela leva ao formulário com os campos já entendidos.

#### Cadastro por formulário `/register/form`

Os mesmos campos, aceites e regras, numa página só, com `FieldGroup`. Erros do servidor aparecem nos campos. Abrir a partir do chat preenche o que já foi entendido.

#### Entrar `/sign-in`

E-mail, senha e o link para cadastro. O erro é sempre "Email or password is incorrect."

#### Conta `/account`

Abas **Profile**, **Conversations** e **Privacy**.

- **Profile:** edição dos campos, com os opcionais sensíveis só visíveis se a personalização estiver ativa.
- **Conversations:** lista com data e primeira pergunta. Vazio: "No conversations yet."
- **Privacy:** interruptores de consentimento com a data de cada aceite, Export my data, Delete my account com `AlertDialog` que exige digitar DELETE, e o link para o canal de pedidos.

#### Privacidade `/privacy`

O Aviso de Privacidade em seções curtas e com âncoras, a lista de operadores com país e finalidade, os dois cookies e o formulário do canal do titular.

#### Visão geral do admin `/admin`

A tela que segue mais de perto a imagem de referência.

- Linha de quatro `StatCard`: Questions, Answered rate, Not in sources rate e Helpful rate, nos últimos 7 dias, com `DeltaBadge` contra os 7 dias anteriores.
- `TrendChartCard` "Questions over time" com cursor, tooltip e seletor de período.
- `SegmentedStatusCard` "Outcomes" com abas Outcome, Intent e Feedback.
- `GroupedBarCard` "Registration funnel" com chat contra formulário por etapa.
- Card de orçamento diário de tokens com `Progress`, em `--warning` acima de 80%.

#### Documentos `/admin/documents`

`DataTable` com título, versão ativa, status e data. `FileDropzone` no topo. Linhas em processamento mostram `Badge` em `--info`. Falhas mostram o erro e a ação Retry. Substituir abre um `Sheet`.

#### Qualidade `/admin/quality`

`DataTable` de conversas filtrável por desfecho, feedback e período, com identidade pseudonimizada. A linha abre um `Sheet` inspetor com as mensagens, a versão do prompt, o `request_id`, o link para o rastro no LangSmith e a ação Reveal identity, que pede um motivo.

#### Pedidos de titular `/admin/privacy`

`DataTable` com tipo, contato, recebido em e `DueDateBadge`. Atrasados primeiro, em `--danger`. A linha abre o detalhe com status e nota de resolução.

### 15.6 Padrões de experiência com IA

| Padrão | Aplicação |
|---|---|
| Declarar que é IA | `SafetyNotice` permanente e a primeira mensagem do cadastro |
| Mostrar fontes | `CitationChip` e `SourceList` em toda resposta de fato |
| Mostrar incerteza | Abstenção e substituição têm badge e texto próprios. O modelo não finge certeza. |
| Mostrar o que a IA entendeu | `ProfileSummaryCard` no cadastro |
| Dar controle | Stop, Retry, editar campos, usar o formulário |
| Proteger o que a IA não deve ver | Senha fora do chat, aviso de saúde no compositor |
| Fechar o ciclo | Feedback útil ou não útil, que vai para a fila de anotação do LangSmith |
| Falhar bem | Degradação para resposta fixa e formulário |

### 15.7 Diretrizes de texto

- Inglês simples, frases curtas, nível de leitura de ensino fundamental.
- Sempre um próximo passo.
- Sem culpar a pessoa: "We couldn't verify that" e não "Your question is invalid".
- Sem antropomorfizar: "Atrium can't" e não "I feel".
- Números e horários no formato do catálogo da seção 9.
- Todo texto fica em `src/i18n/en.ts`.

### 15.8 Acessibilidade

- WCAG 2.2 nível AA.
- Link para pular ao conteúdo. Foco movido para o título da página na troca de rota.
- `ChatThread` usa uma região `aria-live="polite"` que anuncia a resposta completa no `done`, não cada token. Durante a geração, a mensagem tem `aria-busy="true"`.
- Alvos de toque de pelo menos 44 por 44 px no celular e 24 por 24 px no desktop.
- Atalhos: `⌘K` ou `Ctrl+K` para a paleta, `Esc` para fechar, `Enter` para enviar e `Shift+Enter` para quebrar linha.
- Gráficos têm tabela equivalente acessível e resumo em texto.
- Erros nunca dependem só da cor.
- Movimento reduzido em toda a interface, seção 16.4.
- Axe roda em cada página nos testes do Playwright.

### 15.9 Validação de usabilidade

- Antes do deploy público, um teste com 5 pessoas por persona de visitante, cobrindo J1 a J5. Cada tarefa tem critério de sucesso e tempo.
- Métricas acompanhadas no servidor, sem análise no navegador: conclusão do cadastro por caminho, etapa de abandono, taxa de útil, taxa de abstenção e tempo até o primeiro token.
- Um problema de severidade alta encontrado no teste bloqueia o deploy público.

## 16. Movimento com GSAP

### 16.1 Princípios

1. O movimento explica uma mudança de estado: algo chegou, algo foi entendido, algo mudou de lugar.
2. Curto: de 120 a 450 ms na interface. Só a revelação de gráfico chega a 800 ms.
3. Sem laço decorativo. O único laço é o caret durante a geração, porque indica atividade.
4. Só `transform` e `opacity`. Nunca `width`, `height`, `top`, `left`, `margin` ou `padding`.
5. Movimento reduzido sempre respeitado.

### 16.2 Tokens

| Token | Valor | Uso |
|---|---|---|
| `duration.instant` | 0,12 s | Hover e press |
| `duration.fast` | 0,18 s | Saídas, tooltips e menus |
| `duration.base` | 0,28 s | Entradas de conteúdo, padrão global |
| `duration.slow` | 0,45 s | Troca de passo e cartões grandes |
| `duration.chart` | 0,8 s | Revelação de gráfico |
| `ease.enter` | `power2.out` | Entradas, padrão global |
| `ease.exit` | `power2.in` | Saídas |
| `ease.move` | `power3.inOut` | Mudança de posição e Flip |
| `ease.confirm` | `back.out(2)` | Só o ícone de confirmação de campo |
| `stagger.list` | 0,05 s | Cards e listas |
| `distance.enter` | 8 px | Deslocamento vertical de entrada |

`src/motion/gsap.ts` registra `useGSAP` e `Flip` uma vez e chama `gsap.defaults({ duration: 0.28, ease: "power2.out" })`.

### 16.3 Catálogo

| ID | Elemento | Gatilho | Animação | Com movimento reduzido |
|---|---|---|---|---|
| M1 | Conteúdo da rota | Troca de rota | `autoAlpha` de 0 a 1 e `y` de 8 a 0. Cards com `stagger.list`. | Aparece direto |
| M2 | `StatCard` | Dados carregados | O número sobe de 0 ao valor, com `snap` em inteiro e só no texto visível. O valor final fica no `aria-label` desde o início. | Valor final direto |
| M3 | `TrendChartCard` | Montagem | A área e a linha se revelam da esquerda com `scaleX` e `transformOrigin` à esquerda, em `duration.chart` | Gráfico completo direto |
| M4 | Cursor e tooltip do gráfico | Ponteiro | `gsap.quickTo` em `x` e `y`, 0,2 s | Pula para a posição |
| M5 | `UserMessage` | Envio | `autoAlpha` e `y` de 6 a 0 | Aparece direto |
| M6 | `AssistantMessage` | Evento `meta` | `autoAlpha` do contêiner. Tokens não são animados um a um. | Aparece direto |
| M7 | `StreamingCaret` | Durante a geração | Opacidade entre 1 e 0,3, `repeat: -1`, `yoyo`, 0,6 s. Removido no `done`. | Caret estático |
| M8 | `CitationChip` | Eventos `citation` | Entrada com `stagger` de 0,04 s, `scale` de 0,9 a 1 | Aparecem direto |
| M9 | Substituição | Evento `replace` | O rascunho sai com `autoAlpha` em `duration.fast`, a resposta segura entra em `duration.base` | Troca direta |
| M10 | Campo entendido no `ProfileSummaryCard` | Turno do cadastro com campo novo | Uma camada de destaque vai a 1 e volta a 0 em opacidade, e o ícone de confirmação vai de `scale` 0,6 a 1 com `ease.confirm` | Ícone aparece direto, sem destaque |
| M11 | `RegistrationStepper` | Troca de passo | A barra de progresso muda `scaleX` com `ease.move` | Muda direto |
| M12 | `PasswordCard` | `next_step = password` | `autoAlpha` e `y` de 12 a 0 em `duration.slow`. O foco vai para o campo no `onComplete`. | Aparece direto e recebe o foco |
| M13 | `AppSidebar` | Recolher e expandir | Flip registra o estado, a classe muda e Flip anima as posições com `ease.move`. Rótulos saem com `autoAlpha`. | Muda direto |
| M14 | Paleta de comandos, diálogos, sheets e menus | Abrir e fechar | Hook `useGsapPresence` com `forceMount` do Radix: entrada com `autoAlpha` e `scale` de 0,98 a 1, saída em `duration.fast` com `ease.exit` antes de desmontar | Aparece e some direto |
| M15 | `SegmentedStatusCard` | Mudança de contagem | Segmentos mudam `scaleX` com `ease.move` | Muda direto |
| M16 | Botões | Pressionar | `scale` 0,98 em `duration.instant` | Sem escala |

Duas exceções ficam fora do GSAP, com o mesmo token de duração: a animação interna do Sonner e o pulso do Skeleton. O pulso do Skeleton é desligado com movimento reduzido.

ScrollTrigger não é usado na versão 1, porque não há páginas longas de rolagem.

### 16.4 Movimento reduzido

- Um `MotionProvider` cria um `gsap.matchMedia()` com as condições `reduceMotion: "(prefers-reduced-motion: reduce)"`, `isDesktop` e `isMobile`.
- A conta tem a preferência Reduce motion, com os valores System, On e Off, guardada no `localStorage`. Mudar a preferência chama `gsap.matchMediaRefresh()`.
- Os presets em `src/motion/presets.ts` recebem a condição e usam `gsap.set` quando o movimento está reduzido. Nenhum componente decide isso sozinho.

### 16.5 Regras de implementação

- Use `useGSAP` com `scope` apontando para a ref do componente. Nunca seletor sem escopo.
- Animações criadas em handlers de evento passam por `contextSafe`.
- Use `autoAlpha` em vez de `opacity` para entradas e saídas, para um elemento invisível não bloquear cliques.
- Use `clearProps` no fim das entradas, para o CSS voltar a mandar.
- `will-change: transform` só em elementos que estão animando.
- Prefira timelines a encadear `delay`.
- Nada de GSAP em teste de unidade com tempo real. Os testes forçam movimento reduzido.

### 16.6 Testes de movimento

- Vitest com `matchMedia` simulado confere que cada preset chama `gsap.set` quando o movimento está reduzido.
- O Playwright roda as jornadas com `reducedMotion: "reduce"` para capturas estáveis, e uma vez sem redução para pegar erros de animação.
- Um teste confere que o foco chega ao campo de senha depois de M12, com e sem redução.

