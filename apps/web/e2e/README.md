# e2e

Testes de ponta a ponta com Playwright, em duas suítes: uma com a API simulada por `page.route` e outra com a API de verdade no adaptador `demo`. Elas percorrem as jornadas da seção 15.3 do SDD, como pede a seção 21.1.

## Arquivos

| Arquivo | O que prova ou faz | O que cobre |
|---|---|---|
| [api.ts](api.ts) | Falso da conversa: `installConversationApi` responde às rotas de `/v1` com o fluxo SSE escrito à mão. Também traz `expectNoSeriousViolations`, o axe das duas suítes, e `visitingQuestion`, a sugestão do horário de visita | Seções 7.1 e 15.8. Usado pelas duas suítes |
| [account-api.ts](account-api.ts) | Falso da conta: `installAccountApi` guarda o membro em memória e devolve um `AccountApi`, que o teste lê para conferir o que a tela mandou | Seções 11.5 e 12. Usado por `account.spec.ts` |
| [registration-api.ts](registration-api.ts) | Falso do cadastro: `installRegistrationApi` imita a máquina de estados, e `registerByChat` faz a J3 inteira na tela | Seções 7.2, 8.5 e 12. Usado por `registration.spec.ts` e `motion.spec.ts` |
| [journeys.spec.ts](journeys.spec.ts) | J1 com a fonte e a recarga da conversa, J2 com a recusa e o aviso de privacidade no lugar da pergunta, e o axe em `/ask` | J1, J2, FR-1, FR-3 |
| [registration.spec.ts](registration.spec.ts) | J3 pulando os opcionais e J4 com o nome do chat no formulário, a senha vazia e a personalização desligada | J3, J4, FR-5, FR-6 |
| [account.spec.ts](account.spec.ts) | J5: corrigir o perfil, ligar e desligar a personalização, exportar e excluir com a palavra de confirmação. Depois, a aba de privacidade a 375 px | J5, FR-9, seção 11.5 |
| [privacy.spec.ts](privacy.spec.ts) | J8 do lado do visitante, com o corpo do pedido conferido, e a página dos Termos com a versão vigente | J8, FR-16, seção 11.11 |
| [admin-privacy.spec.ts](admin-privacy.spec.ts) | J8 do lado do admin: o pedido atrasado vem primeiro, e o fechamento leva a nota. Confere o corpo de cada `PATCH` | J8, FR-16, seção 12 |
| [motion.spec.ts](motion.spec.ts) | J1 e J3 com o movimento ligado, sem nenhum `pageerror` | NFR-15, seções 16.3 e 16.6 |
| [live/credentials.ts](live/credentials.ts) | E-mail e senha do admin da e2e, que a config passa à API como `ADMIN_EMAIL` e `ADMIN_PASSWORD` | Seção 10.5 |
| [live/fixtures.ts](live/fixtures.ts) | O `test` da suíte ao vivo, com as fixtures automáticas `visitorAddress` (um IP por teste) e `cspViolations` (falha com uma recusa da CSP), mais `uniqueEmail`, `registerByForm`, `signInAsAdmin` e `signIn` | Seções 10.4, 13.3 e 13.4 |
| [live/a11y.ts](live/a11y.ts) | `smallTargets` mede os alvos de toque com as exceções do WCAG 2.5.8, e `tabTo` leva o foco ao alvo com Tab. `expectTouchTargets` não tem uso hoje | NFR-14, seção 15.8 |
| [live/journeys.live.spec.ts](live/journeys.live.spec.ts) | J1, J2, J3, J4, J5 e J8 contra a API, o banco e o proxy de verdade, com o axe em cada página | Seção 15.3, FR-2, FR-17, ADR-014 |
| [live/audit.live.spec.ts](live/audit.live.spec.ts) | Axe e alvos de toque em todas as telas e diálogos, em três testes: público, membro e admin | NFR-14, seção 15.8, Etapa 9.1 |
| [live/keyboard.live.spec.ts](live/keyboard.live.spec.ts) | J1 a J5 só com teclado, no desktop | NFR-14, seção 15.8, Etapa 9.1 |
| [live/performance.live.spec.ts](live/performance.live.spec.ts) | LCP, CLS, INP e JavaScript inicial de `/` no Pixel 5 com Slow 4G e CPU 4 vezes mais lenta. Grava `test-results/desempenho.json` | Seção 5.3, Etapa 9.1 |

## Como ler

As duas suítes dividem a pasta:

| | Simulada | Ao vivo |
|---|---|---|
| Arquivos | `*.spec.ts` na raiz de `e2e` | `live/*.live.spec.ts` |
| Configuração | [playwright.config.ts](../playwright.config.ts) | [playwright.live.config.ts](../playwright.live.config.ts) |
| Servidores | `pnpm dev` em `127.0.0.1:4173` | A API com `uvicorn` em `127.0.0.1:8000`, depois de migrações, `bootstrap_admin` e semente. O build no `vite preview` em `127.0.0.1:4173`, com o proxy de `/backend` e os cabeçalhos de `security-headers.ts` |
| API e banco | Simulados por `page.route` em cada teste. Sem banco | API de verdade com o adaptador `demo`, sobre o PostgreSQL com pgvector de `DATABASE_URL` |
| Projetos | `mobile` (Pixel 5, movimento reduzido) roda tudo menos `motion.spec.ts`. `animation` (Desktop Chrome, sem redução) roda só ele | `live` (Pixel 5, movimento reduzido) roda jornadas, auditoria e desempenho. `live-desktop` (Desktop Chrome, sem redução) roda auditoria e teclado |
| Testes | 12, em 6 arquivos | 18, em 4 arquivos |
| Nova tentativa | 1 na CI, com rastro gravado na nova tentativa | Nenhuma, porque o backend é determinístico. Rastro guardado em falha |
| Job da CI | `web` | `e2e` |

A simulada pega depressa uma quebra de tela. A ao vivo pega o que a simulada não vê: contrato, proxy, cookie, `Origin` e CSP (ADR-014). As duas cobrem J1, J2, J3, J4, J5 e J8. J6 e J7, do admin, ficam fora: a auditoria só abre as telas e os diálogos delas.

Ordem sugerida:

1. [api.ts](api.ts) e [journeys.spec.ts](journeys.spec.ts): o falso mais simples, com o fluxo SSE escrito à mão.
2. [registration-api.ts](registration-api.ts) e [registration.spec.ts](registration.spec.ts): um falso com estado, que anda pelos passos do cadastro.
3. [account.spec.ts](account.spec.ts), [privacy.spec.ts](privacy.spec.ts), [admin-privacy.spec.ts](admin-privacy.spec.ts) e [motion.spec.ts](motion.spec.ts).
4. [playwright.live.config.ts](../playwright.live.config.ts), [live/credentials.ts](live/credentials.ts) e [live/fixtures.ts](live/fixtures.ts): como a suíte ao vivo sobe a API e o banco e isola cada teste.
5. [live/journeys.live.spec.ts](live/journeys.live.spec.ts), depois [live/a11y.ts](live/a11y.ts) com a auditoria e o teclado, e por fim o desempenho.

Conceitos que ajudam:

- **`page.route`** intercepta os pedidos do navegador a `**/backend/v1/**` e responde no lugar da API. O estado do falso fica em variáveis do próprio teste.
- **Fixtures** nascem com `test.extend`. Com `auto: true`, valem em todo teste sem o teste pedir.
- **`expect.soft`** registra a falha e deixa o teste seguir, para uma rodada mostrar todas as falhas da auditoria.
- **`webServer`** da config sobe os servidores e espera a URL responder antes do primeiro teste.
- **`reducedMotion`** do projeto emula `prefers-reduced-motion`.
- **CDP**, o protocolo do Chromium, limita a rede e a CPU no teste de desempenho.

Detalhes que surpreendem:

- Nenhum teste limpa o banco da suíte ao vivo. Cada conta usa `uniqueEmail`, e cada teste manda um `X-Forwarded-For` próprio, na faixa 198.18.0.0/15, porque os limites por IP da seção 10.4 também valem na e2e.
- O admin do `bootstrap_admin` entra a primeira vez pelo novo aceite dos Termos em `/legal/accept` (seção 13.3). O `signInAsAdmin` aceita e segue.
- A config ao vivo sobe a API com `APP_ENV=test`, `GEMINI_API_KEY` vazia, `LANGSMITH_TRACING=false`, `LLM_DAILY_TOKEN_BUDGET=0`, que desliga o teto, e `RETRIEVAL_MIN_SIMILARITY=0.3`, o piso do embedding lexical do `demo` (seção 17).
- Na medida de desempenho, o tamanho do JavaScript inicial e o CLS reprovam sempre. LCP e INP reprovam fora da CI e, na CI, viram anotação no relatório (seção 21.1).
- A fila do admin conta os prazos a partir do `generated_at` da resposta, não do relógio da máquina. Por isso o falso de `admin-privacy.spec.ts`, com datas de 2031, mostra sempre 5 dias de atraso.
- O roteador não tem rota `*` nem `ErrorBoundary` na raiz, então `/nao-existe` mostra a tela de erro padrão do React Router, e a auditoria a audita assim mesmo. A Etapa 14.1 cria a página em português.
- No `keyboard.live.spec.ts`, a J3 devolve o foco ao campo com `focus()`: o campo do cadastro fica `disabled` durante o turno e perde o foco.

## Testes

Em `apps/web`, depois de `pnpm exec playwright install chromium` na primeira vez:

```bash
# Suíte simulada. O Playwright sobe o pnpm dev na porta 4173. `pnpm e2e` faz o mesmo.
pnpm exec playwright test

# Suíte ao vivo, contra um PostgreSQL com pgvector vazio ou descartável.
DATABASE_URL=postgresql://atrium:atrium@127.0.0.1:5432/atrium_e2e pnpm exec playwright test -c playwright.live.config.ts
```

- Sem `DATABASE_URL`, a config ao vivo para com erro antes do primeiro teste.
- A API sobe com `uv run` em `apps/api`, então o `uv` precisa estar no PATH e as dependências da API, instaladas.
- Fora da CI, as duas configs reaproveitam o servidor que já responde na porta (`reuseExistingServer`). Uma API com outra configuração na porta 8000, como a do `docker compose` com o adaptador `fake`, faz a suíte ao vivo falhar.
- Prefira um banco novo a cada rodada da suíte ao vivo. Os IPs de teste se repetem de uma rodada para outra, e os limites por IP da seção 10.4 somam as rodadas que caem na mesma janela.
- `--project mobile`, `--project animation`, `--project live` ou `--project live-desktop` roda um projeto só.

Na CI (`.github/workflows/ci.yml`):

- O job `web` instala o Chromium e roda a suíte simulada, depois do Vitest e antes do build.
- O job `e2e` sobe o PostgreSQL `pgvector/pgvector:pg18` como serviço e roda a suíte ao vivo, com até 25 minutos. Numa falha, `apps/web/test-results` vira o artefato `e2e-traces`, guardado por 7 dias. O job `web` não guarda artefato.

Os rastros e o `desempenho.json` ficam em `apps/web/test-results`. Um rastro abre com `pnpm exec playwright show-trace <arquivo trace.zip>`.

## Leia também

- [SDD 21.1, CI padrão](../../../docs/sdd/entrega.md#211-ci-padrão): as duas suítes e o que reprova na medida de desempenho.
- [SDD 15.3, Jornadas](../../../docs/sdd/experiencia.md#153-jornadas) e [SDD 15.8, Acessibilidade](../../../docs/sdd/experiencia.md#158-acessibilidade).
- [SDD 16.6, Testes de movimento](../../../docs/sdd/experiencia.md#166-testes-de-movimento).
- [SDD 5.3, Metas para medir](../../../docs/sdd.md#53-metas-para-medir) e as medidas da Etapa 9.1 em [acessibilidade e desempenho](../../../docs/acessibilidade-e-desempenho.md).
- [SDD 13.4, Desenvolvimento local e produção](../../../docs/sdd/experiencia.md#134-desenvolvimento-local-e-produção): o proxy e os cabeçalhos que o `vite preview` repete.
- [SDD 10.4, Limites de taxa](../../../docs/sdd/seguranca.md#104-limites-de-taxa).
- [ADR-014, adaptador `demo`](../../../docs/adr/014-adaptador-demo.md).
- [Workflows do GitHub Actions](../../../.github/workflows/README.md): os jobs `web` e `e2e`.
- [Testes do Vitest](../src/test/README.md).
- [Guia, parte 13: testes](../../../docs/guia/13-testes.md).
