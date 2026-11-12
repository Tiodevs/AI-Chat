# test

Configuração comum dos testes de tela e de componente do Vitest. A pasta guarda só o `setup.ts`; cada teste fica ao lado do código que prova. Seção 21.1 do SDD.

## Arquivos

| Arquivo | O que faz | Quem usa |
|---|---|---|
| [setup.ts](setup.ts) | Registra os matchers do `@testing-library/jest-dom`. Troca o `window.matchMedia` por um que responde pelo `window.__media`, e cada teste começa no desktop com movimento reduzido. Põe um `ResizeObserver` vazio, que o jsdom não tem, e dá 3 s às consultas `findBy` e ao `waitFor` (`asyncUtilTimeout`), porque as rotas de admin carregam o Recharts sob demanda. Antes de cada teste, limpa o `localStorage` e o `sessionStorage`, marca `lang="pt-BR"` e `data-motion="reduce"` e troca o `fetch` por um `vi.fn` que responde 401 `unauthenticated` a tudo, como um visitante sem sessão. Depois de cada teste, desmonta a tela e limpa o `queryClient` do app, o estado da conversa (`resetAskState`, que aborta os fluxos abertos), o do atendimento humano e o do console (`resetHandoffState` e `resetAttendanceState`) e os globais trocados | O projeto `dom` do Vitest, pelo `setupFiles` do [vite.config.ts](../../vite.config.ts). O projeto `node` não carrega o arquivo |

## Como ler

1. O bloco `test` do [vite.config.ts](../../vite.config.ts). O Vitest roda em dois projetos. O `dom` usa jsdom e o `setup.ts`, para telas e componentes. O `node` roda sem DOM só os testes de `src/eslint` e `src/deploy`, que leem código e configuração; o do ESLint saiu do jsdom na Etapa 11.1, porque disputava a CPU com as telas. A pasta `e2e` fica de fora dos dois.
2. O [setup.ts](setup.ts), que define o ponto de partida de todo teste do projeto `dom`.
3. Um teste de regra pura, como [model.test.ts](../features/ask/model.test.ts), e depois um teste de tela, como [account.test.tsx](../features/account/account.test.tsx).

Conceitos que ajudam:

- **O `fetch` simulado.** Não há MSW, embora a seção 21.1 o cite. Cada teste de tela troca o `fetch` com `vi.stubGlobal` por uma API falsa escrita no próprio arquivo (`installApi`, `signIn`, `installPasswordStep`), que responde por `MÉTODO caminho`, com o caminho sem `/backend`. Os arquivos não compartilham esses ajudantes: `json`, `renderAt` e `installApi` se repetem em cada um, com pequenas diferenças, como a resposta para a rota desconhecida (401 ou 404).
- **As rotas reais.** Os testes de tela abrem as `routes` de `app/router.tsx` num `createMemoryRouter`, dentro do `AppProviders` (TanStack Query e `MotionProvider`). Assim os loaders e as guardas da seção 13.3 rodam de verdade.
- **`findBy` em vez de `getBy`.** O que carrega sob demanda, como a barra lateral, as rotas e o Recharts, é esperado com `findBy` (seção 21.1). `auth.test.tsx` e `insights.test.tsx` importam as rotas de admin num `beforeAll` de 30 s, para a primeira compilação não gastar os 3 s da consulta.
- **Movimento.** O `setup.ts` força o movimento reduzido (seção 16.5). Para ligar o movimento, um teste grava `atrium.motion-preference` como `off` no `localStorage` e troca a função do GSAP que roda, como em `registration.test.tsx`; os presets são testados com o GSAP trocado por espiões. Para simular o celular, o teste troca o `window.__media`.
- **Acessibilidade.** Oito arquivos de tela rodam o `axe-core` e falham com violação séria ou crítica (NFR-14, seção 15.8). Um `Sheet` abre num portal, fora do `container`, e por isso `privacy-queue.test.tsx` roda o axe do detalhe no `document.body`.

## Testes do frontend

São 18 arquivos e 161 testes: 153 em 16 arquivos do projeto `dom` e 8 em 2 arquivos do `node`. O `vitest list` mostra 130, porque conta cada `it.each` uma vez só.

| Arquivo | Projeto | Testes | O que prova | Requisitos e seções |
|---|---|---|---|---|
| [app/shell.test.tsx](../app/shell.test.tsx) | `dom` | 24 | Foco no título e `document.title` na troca de rota, guardas que levam a `/sign-in?returnTo=`, navegação do visitante no desktop e no celular, barra lateral do membro, saída da conta com e sem falha, menu do celular, link para pular ao conteúdo, barra recolhida, preferência de movimento e axe em `/` | NFR-14, NFR-15, seções 13.3, 14.5, 14.6, 15.8, 16.3 (M13) e 16.4 |
| [components/patterns/assistant-message.test.tsx](../components/patterns/assistant-message.test.tsx) | `dom` | 2 | A citação agrupada, como `[2, 3]`, vira um chip por fonte; um grupo com fonte desconhecida fica como texto | FR-2, seções 7.1 e 14.6 |
| [deploy/vercel-config.test.ts](../deploy/vercel-config.test.ts) | `node` | 4 | O `vercel.ts` declara só `routes`, só a rota da API leva o `x-atrium-edge` com o `EDGE_SECRET`, as rotas são as que a Vercel gerava antes da Etapa 12.5, e `/backend`, a SPA e `/assets` caem no destino certo | Seções 10.3, 13.4 e 22.2 |
| [eslint/restrictions.test.ts](../eslint/restrictions.test.ts) | `node` | 4 | O ESLint barra `fetch` e `@/lib/api` num componente, deixa o cliente num hook de feature sem `fetch` e libera `fetch` em `src/lib` | NFR-1, seções 6.2 e 13.2 |
| [features/account/account.test.tsx](../features/account/account.test.tsx) | `dom` | 18 | Regras do perfil; correção com erro de campo do servidor, campos sensíveis só com a personalização, preferência de movimento, lista de conversas, consentimentos, exportação, exclusão com EXCLUIR e a recusa ao admin; novo aceite legal antes de continuar e depois do login | FR-9, NFR-14, NFR-15, seções 10.5, 11.5, 12, 13.3, 15.5 e 16.4 |
| [features/admin/documents.test.tsx](../features/admin/documents.test.tsx) | `dom` | 11 | Status de cada documento, limite de 10 MB e tipos no navegador, ações por estado, barra lateral do admin, envio em multipart, erro de campo do servidor, substituição pelo `Sheet`, nova tentativa, arquivamento com confirmação e axe | FR-10, FR-11, FR-12, NFR-10, NFR-14, seções 12, 14.5, 15.3 (J6) e 15.5 |
| [features/admin/insights.test.tsx](../features/admin/insights.test.tsx) | `dom` | 9 | Variação em porcentagem e em pontos percentuais; indicadores, tabelas equivalentes aos gráficos, orçamento e período da visão geral; qualidade pseudonimizada com filtro, inspetor com o link do rastro (J7), revelação só com motivo e axe | FR-15, NFR-14, seções 11.8, 12, 15.3 (J7), 15.5, 15.8 e 16.3 (M2) |
| [features/admin/privacy-queue.test.tsx](../features/admin/privacy-queue.test.tsx) | `dom` | 7 | Prazo em texto do `DueDateBadge`, `mailto:` só para endereço seguro, atrasados primeiro com texto e cor, status e fechamento com nota, erro de campo e 409 com releitura da fila, pedido fechado só para leitura e axe na lista e no detalhe | FR-16, NFR-14, seções 11.5, 12, 14.6, 15.5 e 15.8 |
| [features/ask/ask.test.tsx](../features/ask/ask.test.tsx) | `dom` | 4 | No hook `useAskConversation`, `replace` troca o rascunho e o anúncio espera o `done`, Stop aborta o pedido e a consulta de reserva roda a cada segundo quando o primeiro evento não chega; a região ao vivo do `ChatThread` recebe a resposta inteira só no `done` | FR-18, seções 7.1, 13.2, 15.5 e 15.8 |
| [features/ask/model.test.ts](../features/ask/model.test.ts) | `dom` | 4 | Funções puras da conversa: `replace`, anúncio só no `done`, pergunta médica escondida pelo marcador e limite de taxa em minutos | FR-17, seções 7.1, 10.4, 11.4 e 15.8 |
| [features/auth/auth.test.tsx](../features/auth/auth.test.tsx) | `dom` | 10 | `safeReturnTo` e o limite em minutos; login com erro de credenciais, limite e `returnTo`; página 403, conta do membro e error boundary com o `request_id`; axe | NFR-14, seções 10.4, 13.3 e 15.5 |
| [features/privacy/privacy.test.tsx](../features/privacy/privacy.test.tsx) | `dom` | 11 | Regras do canal; Aviso com operadores, cookies, versão, contato e âncoras; pedido sem conta com prazo, campos obrigatórios, limite diário e e-mail de quem está na conta; Termos com seções e versão; axe | FR-16, NFR-14, seções 10.4, 11.5, 11.7, 11.9, 11.11, 12 e 15.5 |
| [features/registration/model.test.ts](../features/registration/model.test.ts) | `dom` | 6 | Funções puras do cadastro: etapa visível, força da senha em texto, campos do chat com a senha vazia, aceites obrigatórios, e-mail já usado e o corpo do formulário | FR-6, FR-7, FR-8, seções 7.2, 8.5 e 16.3 (M11) |
| [features/registration/registration.test.tsx](../features/registration/registration.test.tsx) | `dom` | 11 | Cartão de resumo por turno, e-mail já usado, dúvida no chat, modelo indisponível, foco na senha depois de M12 com e sem redução, `ConsentFieldSet`, erro de campo do formulário, formulário vindo do chat, Usar o formulário com o turno a caminho (J4) e axe | FR-5, FR-6, FR-8, NFR-14, seções 7.2, 8.5, 12, 15.3 (J4), 15.5, 16.3 (M12) e 16.6 |
| [lib/sse.test.ts](../lib/sse.test.ts) | `dom` | 3 | O leitor SSE junta eventos partidos entre leituras, ignora o `: keepalive` e entrega o último evento quando o fluxo fecha | Seções 7.1, 13.1 e 21.1 |
| [motion/presets.test.ts](../motion/presets.test.ts) | `dom` | 30 | Cada um dos 20 presets usa `gsap.set` com movimento reduzido; M1 a M13 e M15 com os tokens, o foco no fim de M12 e o Flip só com `transform`; os presets não carregam o Flip | NFR-15, seções 5.3, 16.2, 16.3, 16.4 e 16.6 |
| [styles/contrast.test.ts](../styles/contrast.test.ts) | `dom` | 2 | Cada par de token de texto e de fundo passa em 4,5:1, e a conferência falha abaixo disso | NFR-14, seção 14.2 |
| [styles/raw-color.test.ts](../styles/raw-color.test.ts) | `dom` | 1 | Cor crua só em `styles/tokens.css`, comentários inclusive | Seções 14.2 e 14.8 |

Os itens de frontend da seção 21.1 ficam assim: o leitor SSE em `lib/sse.test.ts`; `replace` em `features/ask/model.test.ts` e `features/ask/ask.test.tsx`; Stop em `features/ask/ask.test.tsx`; o erro de campo do servidor, o cartão de resumo e o `ConsentFieldSet` em `features/registration/registration.test.tsx`; os presets em `motion/presets.test.ts`; o contraste em `styles/contrast.test.ts`. Da tabela da mesma seção, a importação de arquitetura do frontend é `eslint/restrictions.test.ts`, e as rotas da Vercel são `deploy/vercel-config.test.ts`.

## Testes

Em `apps/web`:

```bash
pnpm test                                        # vitest run, os dois projetos
pnpm exec vitest run --project dom               # só telas e componentes
pnpm exec vitest run --project node              # só ESLint e Vercel
pnpm exec vitest run src/features/ask/ask.test.tsx   # um arquivo
pnpm exec vitest                                 # modo de observação
```

Nenhum teste chama a API, o Gemini ou o LangSmith (NFR-3), e nenhum precisa de banco. Na CI, o job `web` do `ci.yml` roda `pnpm test` depois do ESLint e do `tsc`, e antes do Playwright, do build e do Storybook (seção 22.3).

Com a máquina carregada, por exemplo com o pytest rodando junto, uma consulta `findBy` pode passar dos 3 s e falhar sem defeito. Rode o Vitest sozinho e, numa falha por tempo, rode de novo antes de procurar um bug. A folga maior nessas esperas e o limiar de cobertura são da Etapa 11.4, um débito técnico (seção 6 do plano de ação).

## Leia também

- [SDD 21.1, CI padrão](../../../../docs/sdd/entrega.md#211-ci-padrão)
- [SDD 6.2, teste de arquitetura](../../../../docs/sdd/arquitetura.md#teste-de-arquitetura)
- [SDD 13.3, rotas e guardas](../../../../docs/sdd/experiencia.md#133-rotas-e-guardas)
- [SDD 14.2, tokens de cor](../../../../docs/sdd/experiencia.md#142-tokens-de-cor)
- [SDD 15.8, acessibilidade](../../../../docs/sdd/experiencia.md#158-acessibilidade)
- [SDD 16.4, movimento reduzido](../../../../docs/sdd/experiencia.md#164-movimento-reduzido) e [16.6, testes de movimento](../../../../docs/sdd/experiencia.md#166-testes-de-movimento)
- [A e2e com o Playwright](../../e2e/README.md)
- [Plano de ação, débitos técnicos](../../../../docs/plano-de-acao.md#6-débitos-técnicos)
- [Guia, parte 13: testes](../../../../docs/guia/13-testes.md) e [parte 11: frontend por dentro](../../../../docs/guia/11-frontend-por-dentro.md)
