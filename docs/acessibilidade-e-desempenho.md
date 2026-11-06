# Acessibilidade, movimento e desempenho

Relatório da Etapa 9.1 do [plano de ação](plano-de-acao.md). Ele cobre as seções 5.3, 15.8 e 16 do SDD e os requisitos NFR-14 e NFR-15. As medidas são de 2026-11-06, no fim da etapa.

## Resumo

| Critério | Resultado | Como foi verificado |
|---|---|---|
| CA-1. Axe sem violação séria ou crítica | Passa em 26 telas e diálogos no celular e 24 no desktop | `e2e/live/audit.live.spec.ts` |
| CA-2. Jornadas só com teclado e alvos de 44 px | J1 a J5 passam só com teclado. Nenhum alvo abaixo do mínimo | `e2e/live/keyboard.live.spec.ts` e `audit.live.spec.ts` |
| CA-3. LCP, INP, CLS e JavaScript inicial de `/` | Os quatro dentro da meta | `e2e/live/performance.live.spec.ts` |
| CA-4. Tempo até o primeiro token, p95 abaixo de 3 s | Ainda não medido. Precisa da chave do Gemini em produção | `.github/scripts/ttft.mjs` |

Duas verificações dependem de uma pessoa: a passada com leitor de tela e o Lighthouse em produção. O passo a passo está em [O que falta fazer à mão](#o-que-falta-fazer-à-mão).

## Acessibilidade

### Método

A auditoria roda na suíte ao vivo, a mesma do job `e2e` da CI: a API de verdade com o adaptador `demo` e o frontend com `vite preview` e os cabeçalhos de produção (seção 21.1). Em cada tela e em cada diálogo aberto, ela confere duas coisas:

- **Axe.** Uma violação séria ou crítica reprova.
- **Alvos de toque.** Todo controle visível precisa de 44 por 44 px no celular e 24 por 24 px no desktop (seção 15.8). As exceções são as mesmas do WCAG 2.2 (critério 2.5.8): um link dentro de uma frase, que segue o tamanho do texto, e o que fica escondido para leitores de tela, como o link de pular para o conteúdo antes de receber o foco.

A auditoria roda duas vezes: num Pixel 5 emulado com movimento reduzido e num Chrome de desktop sem redução. No desktop, a navegação fica sempre visível e é auditada junto de cada página, e por isso a conta tem três menus a menos e um estado a mais: a barra lateral recolhida. As falhas se acumulam, então uma execução mostra todas de uma vez.

Telas e diálogos cobertos:

| Quem | Telas e diálogos |
|---|---|
| Visitante | `/`, `/ask`, `/register`, `/register/form`, `/sign-in`, `/privacy`, `/terms`, página não encontrada, conversa com resposta e fontes, menu do visitante e paleta de comandos |
| Membro | Conta nas abas Perfil, Conversas e Privacidade, diálogo de exclusão da conta, menu do membro e a página 403 do admin |
| Admin | Visão geral, documentos, sheet de substituir documento, diálogo de arquivar, qualidade, inspetor de conversa, fila de pedidos de titular, detalhe do pedido, menu do admin no celular e barra lateral recolhida no desktop |

O teclado tem um teste próprio. No desktop, J1 a J5 são feitas só com Tab, Shift+Tab, Enter, Espaço e as setas, sem clique depois de a página abrir. A única exceção é a criação da conta de apoio da J5, que é feita pelo formulário antes do teste.

### Problemas encontrados e correções

| Problema | Critério | Correção |
|---|---|---|
| Botões de 28 e 32 px, campos, o seletor, interruptores e caixas de consentimento abaixo de 44 px no celular | Seção 15.8 | Altura mínima de 44 px abaixo de 768 px em `Button`, `Input`, `SelectTrigger` e nos rótulos de consentimento. No desktop continuam os 24 px |
| Links de Termos e Privacidade fora de frase, menores que 44 px | Seção 15.8 | Altura mínima de 44 px no celular |
| Itens da barra lateral com 32 px no celular | Seção 15.8 | 44 px no celular e 32 px no desktop |
| Logotipo e botão de perfil com nome acessível diferente do texto visível | WCAG 2.5.3 | O logotipo usa o texto visível. O perfil se chama "{nome}, menu da conta" |
| Superfície do gráfico do Recharts focável dentro de um bloco com `aria-hidden` | WCAG 4.1.2 | Camada de acessibilidade do Recharts desligada. A tabela equivalente da seção 15.8 continua sendo o caminho acessível |
| Com o menu do visitante aberto, o resto da página ficava com `aria-hidden` e continuava focável | WCAG 4.1.2 | Disclosure de navegação do WAI-ARIA: botão com `aria-expanded` e uma lista de links, sem diálogo modal. Fecha com Esc, com um toque fora e ao escolher um link |
| O fim da animação de rota (M1) movia o foco para o título mesmo quando a pessoa já digitava na página nova | WCAG 2.4.3 | O título só recebe o foco se ele ainda não estiver dentro da página nova. A J4 só com teclado mostrou o defeito |
| Com a barra lateral recolhida, o link do logotipo e o botão de busca ficavam sem nome: o preset de M13 punha `visibility: hidden` nos rótulos em `sr-only` | WCAG 4.1.2 | Os rótulos nunca recebem `visibility: hidden`. Eles só entram com `autoAlpha` quando a barra expande. A barra já começa recolhida entre 768 e 1023 px |

Depois das correções, as duas passadas da auditoria e as cinco jornadas por teclado passam sem nenhuma violação.

### Movimento

- A suíte ao vivo roda todas as jornadas no celular com `reducedMotion: "reduce"`. A auditoria e as jornadas por teclado rodam no desktop sem redução, o que pega erro de animação, como o roubo de foco acima.
- A suíte com a API simulada continua com a passada sem redução em `e2e/motion.spec.ts`.
- Na primeira carga, M1 não anima: o conteúdo aparece direto, e o LCP não espera a animação.

## Desempenho

### Perfil de medida

- Pixel 5 emulado no Chromium do Playwright.
- Rede do perfil Slow 4G do Lighthouse: 150 ms de ida e volta, 1,6 Mbps de descida e 750 kbps de subida.
- CPU 4 vezes mais lenta.
- Frontend com `vite preview`, que entrega com gzip, e a API de verdade com o adaptador `demo`.

O JavaScript inicial é tudo o que a página pede ao abrir, até a rede parar e antes de qualquer interação. O teste soma o tamanho de cada arquivo com gzip, como a meta mede, e também com brotli, que é o que a Vercel entrega. INP é a maior latência de evento numa interação típica: clicar no campo, digitar e passar o ponteiro por uma sugestão.

### Resultados

| Medida | Meta | Início da etapa | Depois da divisão do código | Fim da etapa (10 execuções) |
|---|---|---|---|---|
| LCP | abaixo de 2,5 s | 2,74 s | de 2,42 a 2,47 s | mediana 2,11 s, de 1,95 a 2,21 s |
| CLS | abaixo de 0,1 | não medido | 0,077 | 0,001 |
| INP | abaixo de 200 ms | não medido | de 32 a 48 ms | mediana 32 ms, máximo 48 ms |
| JavaScript inicial de `/`, gzip | até 200 KB | 225,7 KB | 193,5 KB | 193,5 KB, igual em todas |
| JavaScript inicial de `/`, brotli | | | 169,6 KB | 169,7 KB |

Os tempos variam com a carga da máquina, porque a CPU emulada é 4 vezes mais lenta que a real. Numa máquina ocupada, uma execução chegou a 2,52 s de LCP. Por isso a CI só registra LCP e INP como anotação, enquanto o tamanho do JavaScript e o CLS, que não dependem da velocidade da máquina, reprovam em qualquer lugar.

### O que mudou

1. **Barra lateral, tooltip e paleta de comandos fora do carregamento inicial.** O visitante sem sessão não usa nenhum dos três. A barra lateral carrega sob demanda, com um espaço reservado do mesmo tamanho, e o `TooltipProvider` saiu da raiz para a barra lateral.
2. **Menu do visitante sem o Radix Menu.** O disclosure de navegação tirou o posicionamento flutuante e a camada de diálogo da página inicial do celular.
3. **As rotas de `/` vêm na primeira leva.** O plugin `apps/web/route-preload.ts` põe o shell, a moldura da rota e a página inicial como `modulepreload` no `index.html`. Antes, o navegador só descobria esses arquivos depois de baixar e rodar o JavaScript de entrada. O build falha se uma dessas rotas sumir do bundle.
4. **Barra do topo reservada no celular.** O cabeçalho do visitante só aparecia quando `/v1/me` respondia, e o conteúdo descia 56 px. No celular, o visitante e o membro têm a mesma barra de 56 px, então ela ocupa o lugar desde o início.
5. **Paleta de comandos só no desktop no tempo ocioso.** O atalho ⌘K é de teclado físico. No celular, a paleta só baixa quando alguém abre a busca, o que poupa 12 KB da rede do visitante.

### Caminho do LCP

Com as rotas na primeira leva, o JavaScript e o CSS saem juntos, cerca de 200 ms depois do início. O arquivo de entrada, com 141 KB, chega por volta de 1,55 s. O título da página inicial, que é o elemento do LCP, aparece por volta de 2,1 s, depois de o JavaScript rodar na CPU emulada. Não sobra ida e volta no caminho: o que resta é banda e CPU.

Composição do JavaScript inicial no fim da etapa, com gzip:

| Arquivo | KB |
|---|---|
| Entrada (`index`), com React, React DOM, React Router, TanStack Query, GSAP com o Flip e os providers da aplicação | 140,6 |
| Textos em português (`pt`) | 11,9 |
| Os 21 arquivos das rotas de `/` e dos componentes que elas usam | 41,0 |

Para a próxima redução, os candidatos eram o plugin Flip, registrado na entrada sem nenhum uso, e os textos das telas de admin dentro de `pt`. O Flip já saiu da entrada (veja as pendências).

## Tempo até o primeiro token

O script `.github/scripts/ttft.mjs` mede o primeiro token e a resposta completa pela origem da Vercel, como o navegador:

```bash
node .github/scripts/ttft.mjs https://atrium-gold.vercel.app 20
```

Ele cria uma conversa de convidado, faz uma pergunta de aquecimento fora da conta e faz as 20 perguntas seguintes. São quatro perguntas do conjunto de avaliação, em rodízio. O padrão de 20 fica abaixo do limite de 30 mensagens por hora do convidado (seção 10.4). Só conta resposta `answered`: sem a chave do Gemini, a resposta fixa de indisponibilidade é imediata e não serve de medida, e o script falha. Ele sai com sucesso só se o p95 do primeiro token ficar abaixo de 3 s e o p95 da resposta completa abaixo de 12 s.

Em 2026-11-06, a produção ainda não tinha `GEMINI_API_KEY`, e o CA-4 fica para depois de a chave existir. Do lado da API, o Grafana mostra o mesmo sinal em `atrium_qa_first_token_seconds`.

## Pendências

- **M13 sem o Flip. Resolvida depois da etapa.** A barra lateral animava a largura com uma transição de CSS, contra a regra de animar só `transform` e `opacity`, e o Flip ficava registrado em `src/motion/gsap.ts` sem uso. Agora a largura troca direto e o Flip move os ícones só com `transform`, como pede a seção 16.3. O plugin é registrado em `src/motion/flip.ts`, que vai junto da barra lateral sob demanda. No build, o Flip tirou 8,6 KB com gzip do arquivo de entrada, que caiu de 145,5 para 136,9 KB, e passou para o arquivo da barra lateral, que o visitante sem sessão não baixa.
- **CA-4.** Depende da chave do Gemini em produção.

## O que falta fazer à mão

1. **Lighthouse em `/`, no modo celular.** No Chrome, abra `https://atrium-gold.vercel.app/`, depois DevTools, Lighthouse, Mobile, com as categorias Performance e Accessibility. Pelo terminal: `npx lighthouse https://atrium-gold.vercel.app/ --only-categories=performance,accessibility --view`. O Lighthouse simula a mesma rede e a mesma CPU deste relatório.
2. **Leitor de tela.** Percorra J1 a J5 com o VoiceOver (`⌘F5` no Mac) ou o NVDA no Windows. Confira se cada página nova anuncia o título, se a resposta do assistente é lida uma vez, no fim, e se os erros de formulário são lidos junto do campo.
3. **Tempo até o primeiro token.** Depois de pôr a chave do Gemini em produção, rode o script acima.

## Como medir de novo

Na pasta `apps/web`, com um PostgreSQL com pgvector descartável:

```bash
DATABASE_URL=postgresql://usuario:senha@127.0.0.1:5432/atrium_e2e pnpm exec playwright test -c playwright.live.config.ts audit keyboard performance
```

O resultado de desempenho fica em `apps/web/test-results/desempenho.json`, com o tamanho de cada arquivo. Para ver a variação, acrescente `--repeat-each=10` e rode só `performance`.
