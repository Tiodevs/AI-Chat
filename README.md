<div align="center">

# Atrium

### Plataforma de atendimento com IA em primeiro lugar, segura e ética

Um assistente que responde visitantes de um hospital usando só informações publicadas, mostra de onde tirou cada resposta e sabe quando não deve responder.

[![CI](https://github.com/Tiodevs/AI-Chat/actions/workflows/ci.yml/badge.svg)](https://github.com/Tiodevs/AI-Chat/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangChain%20%2B%20LangGraph-1C3C3C?logo=langchain&logoColor=white)
![React](https://img.shields.io/badge/React%2019-20232A?logo=react&logoColor=61DAFB)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL%20%2B%20pgvector-4169E1?logo=postgresql&logoColor=white)
![LGPD](https://img.shields.io/badge/LGPD-por%20design-0E9F6E)
[![Licença MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-blue)](LICENSE)
[![PRs bem-vindos](https://img.shields.io/badge/PRs-bem--vindos-ff69b4)](CONTRIBUTING.md)

[Visão geral](#visão-geral) ·
[Telas](#telas) ·
[Como funciona](#por-dentro) ·
[Rodar localmente](#rodar-localmente) ·
[Contribuir](#contribuir) ·
[Licença](#licença)

<br />

<img src="docs/assets/screenshots/conversa.png" alt="Conversa no Atrium: o visitante pergunta onde estacionar e recebe uma resposta com a fonte citada" width="900" />

</div>

<br />

## Visão geral

Muita gente procura um hospital com dúvidas simples: qual é o horário de visita, onde estacionar, por qual entrada chegar. O **Atrium** é um assistente de atendimento que responde essas perguntas na hora, em português, a qualquer momento do dia.

A IA é a porta de entrada, mas não trabalha solta:

- **Responde só com o que o hospital publicou.** Cada resposta mostra a fonte. Se a informação não existe, o Atrium diz que não encontrou e indica o telefone da central, em vez de inventar.
- **Não dá orientação médica.** Perguntas sobre sintomas, diagnóstico ou remédios recebem uma recusa clara, com o caminho para a emergência.
- **Protege quem conversa.** Mensagens sobre saúde não são guardadas, a senha nunca passa pela IA e a pessoa pode exportar ou apagar os próprios dados.
- **Cadastro do jeito que a pessoa preferir.** Uma conversa guiada cria a conta, e um formulário comum fica sempre disponível.
- **Operação visível.** Um painel mostra quantas perguntas foram respondidas, recusadas ou sem resposta, e a equipe revisa conversas pseudonimizadas para melhorar a qualidade.

> [!NOTE]
> O **Harborlight General Hospital**, a cidade de Port Meridian, as pessoas, os telefones e os documentos são fictícios. O hospital é inventado; a engenharia ao redor dele tem forma de produção. O Atrium serve de referência de como construir um produto de IA para o público com responsabilidade.

### Os quatro compromissos

<table>
  <tr>
    <td width="25%" valign="top">
      <h4>🤖 IA primeiro</h4>
      A conversa é a interface principal: perguntas, cadastro e acompanhamento acontecem em linguagem natural, com respostas transmitidas em tempo real.
    </td>
    <td width="25%" valign="top">
      <h4>🛡️ Segurança</h4>
      Proteção contra instruções escondidas em mensagens e documentos, limites de uso, sessões seguras e um orçamento diário que impede gasto descontrolado.
    </td>
    <td width="25%" valign="top">
      <h4>⚖️ Ética</h4>
      A pessoa sempre sabe que fala com uma IA. Nada de diagnóstico, nada de resposta inventada e nenhuma decisão importante tomada pelo modelo.
    </td>
    <td width="25%" valign="top">
      <h4>🔐 Privacidade</h4>
      LGPD desde o desenho: coleta mínima, consentimento por finalidade, retenção com prazo, exportação e exclusão de dados pelo próprio titular.
    </td>
  </tr>
</table>

## Telas

<table>
  <tr>
    <td width="50%" valign="top">
      <img src="docs/assets/screenshots/home.png" alt="Página inicial com campo de pergunta e atalhos" />
      <p align="center"><b>Início.</b> Atalhos para as dúvidas mais comuns e o aviso permanente de que o Atrium é uma IA.</p>
    </td>
    <td width="50%" valign="top">
      <img src="docs/assets/screenshots/guardrail.png" alt="Pergunta sobre sintoma recebe recusa de orientação médica" />
      <p align="center"><b>Limite ético.</b> Uma pergunta sobre sintoma é recusada, a mensagem não é guardada e a pessoa recebe o caminho da emergência.</p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <img src="docs/assets/screenshots/cadastro-ia.png" alt="Cadastro por conversa com a IA" />
      <p align="center"><b>Cadastro com IA.</b> Uma conversa guiada coleta os dados, e a pessoa vê e corrige tudo antes de confirmar.</p>
    </td>
    <td width="50%" valign="top">
      <img src="docs/assets/screenshots/cadastro-formulario.png" alt="Cadastro por formulário" />
      <p align="center"><b>Formulário sempre disponível.</b> Os mesmos dados e consentimentos, para quem prefere não conversar.</p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <img src="docs/assets/screenshots/admin-visao-geral.png" alt="Painel de visão geral do admin" />
      <p align="center"><b>Visão geral.</b> Volume de perguntas, taxa de respostas, abstenções, feedback e funil de cadastro.</p>
    </td>
    <td width="50%" valign="top">
      <img src="docs/assets/screenshots/admin-qualidade.png" alt="Inspetor de qualidade com conversas pseudonimizadas" />
      <p align="center"><b>Qualidade.</b> Conversas pseudonimizadas, filtradas por desfecho e feedback, só de quem consentiu.</p>
    </td>
  </tr>
</table>

<p align="center">
  <img src="docs/assets/screenshots/mobile-conversa.png" alt="Conversa no celular" width="300" />
  <br />
  <sub>A mesma experiência no celular, onde muitos visitantes fazem a pergunta.</sub>
</p>

## O que já funciona

| Área | O que entrega |
|---|---|
| Perguntas | Respostas em tempo real, com citações conferidas contra os documentos recuperados |
| Guardrails | Recusa de orientação médica, fora de tema e abstenção quando a informação não existe |
| Cadastro | Conversa guiada por IA ou formulário, com consentimentos separados por finalidade |
| Conta | Histórico de conversas, exportação dos dados e exclusão da conta |
| Admin | Gestão de documentos, visão geral de uso e inspetor de qualidade |
| Privacidade | Canal do titular, retenção automática e documentos de privacidade (RIPD, ROPA, LIA) |
| Operação | Logs estruturados, rastros OpenTelemetry, métricas Prometheus, painéis Grafana e LangSmith |

O andamento etapa por etapa está no [plano de ação](docs/plano-de-acao.md#4-status-das-etapas). Os próximos passos são a fila de pedidos de titular no admin, o acabamento de acessibilidade e a publicação em produção.

---

# Por dentro

A partir daqui, a parte técnica. A especificação completa está em [`docs/sdd.md`](docs/sdd.md), dividida em seções em [`docs/sdd/`](docs/sdd/). As decisões estruturais estão nos [ADRs](docs/adr/).

## Stack

| Camada | Tecnologia |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, shadcn/ui, Radix UI, Lucide e GSAP |
| API | Python 3.12, FastAPI, Pydantic, SQLAlchemy assíncrono e Alembic |
| IA | LangChain no pipeline de perguntas, LangGraph no cadastro, Gemini atrás de portas próprias |
| Busca | PostgreSQL com pgvector, busca híbrida vetorial e por texto completo |
| Testes | Pytest, Vitest, Testing Library, Playwright e Storybook |
| Observabilidade | OpenTelemetry, Prometheus, Grafana e LangSmith |
| Entrega | GitHub Actions, Vercel (frontend) e Railway (API, banco e monitoramento) |

## Arquitetura

```mermaid
flowchart LR
  visitor[Navegador do visitante]
  admin[Navegador do admin]
  vercel[Vercel: SPA React e rewrite /backend]
  api[FastAPI]
  job[Tarefa de retenção]
  db[(PostgreSQL + pgvector)]
  prom[Prometheus + Grafana]
  gemini[API Gemini]
  langsmith[LangSmith]

  visitor --> vercel
  admin --> vercel
  vercel -->|mesma origem| api
  api --> db
  job --> db
  api --> gemini
  api -.->|rastros mascarados| langsmith
  prom -->|coleta /metrics| api
```

O navegador fala só com a origem do frontend. A Vercel (ou o proxy do Vite, localmente) encaminha `/backend/*` para a API, o que mantém o cookie de sessão primário e dispensa CORS.

A API segue MVC, com o "M" dividido nas camadas que um sistema de IA exige ([SDD 6.2](docs/sdd/arquitetura.md#62-mvc-com-as-camadas-de-que-um-sistema-de-ia-precisa)):

```text
controller → service → workflow → ports ← adapters
     ↓          ↓          ↓
   schema    domain ←──────┘
                ↑
service → unit of work → repository → model
```

O domínio é Python puro. Os workflows recebem as portas pelo construtor e não abrem sessão de banco. Os serviços são donos da transação. Um teste de arquitetura impede que uma camada importe o que não deve.

## Como uma pergunta é respondida

```mermaid
flowchart TD
  q[Pergunta do visitante] --> r[Reescrever e classificar]
  r -->|orientação médica| refuse[Recusa fixa, mensagem não guardada]
  r -->|fora de tema ou baixa confiança| off[Resposta fixa de escopo]
  r -->|informação pública| e[Embedding da pergunta]
  e --> s[Busca híbrida: vetor + texto completo]
  s -->|abaixo do piso de similaridade| abs[Abstenção com telefone da central]
  s -->|contexto encontrado| g[Gerar resposta em fluxo]
  g --> v{Citações e telefones conferem?}
  v -->|sim| ok[Resposta com fontes]
  v -->|não| rep[Substitui pela resposta segura]
```

A resposta chega por Server-Sent Events (`meta`, `token`, `replace`, `citation`, `done`). Cada mensagem gravada guarda o desfecho, as citações, o modelo, a versão do prompt, os tokens, a latência e o id do rastro. Detalhes em [SDD 7.1](docs/sdd/arquitetura.md#71-fazer-uma-pergunta).

## Segurança e ética na prática

- **Contexto não confiável.** Documentos e mensagens entram delimitados e rotulados. O modelo é instruído a ignorar instruções encontradas neles.
- **O modelo não decide.** A máquina de estados do cadastro é Python puro, no domínio. O Gemini só extrai campos e formula a próxima pergunta. `role`, consentimentos e senha não fazem parte do schema da ferramenta.
- **Senha fora da IA.** A senha vai para um endpoint próprio e é guardada como hash argon2id.
- **Fundamentação conferida.** Uma citação só fica se aponta para um trecho realmente recuperado. Telefones na resposta precisam existir no contexto.
- **Sessões e transporte.** Cookies `HttpOnly` e `SameSite=Lax`, conferência de `Origin` em métodos que alteram estado e `Cache-Control: no-store` em toda a API.
- **Limites de uso.** Limites de taxa por e-mail, IP, convidado e usuário, mais um orçamento diário de tokens que degrada o serviço de forma controlada.
- **Prompts versionados.** Cada prompt tem `PROMPT_VERSION`. Um teste falha se o texto muda sem a versão mudar.
- **LGPD.** Inventário de tratamento, consentimento específico para dados que podem revelar saúde, retenção com prazo, direitos do titular e plano de incidentes. Veja [SDD 11](docs/sdd/lgpd.md) e [`docs/privacy/`](docs/privacy/).

Mais em [SDD 10, Segurança](docs/sdd/seguranca.md).

## Estrutura do repositório

```text
.
├── apps/
│   ├── api/            FastAPI, LangChain, LangGraph, Alembic e testes Pytest
│   │   └── app/        controllers, services, workflows, domain, repositories, ports, adapters…
│   └── web/            React, Vite, shadcn/ui, GSAP, Vitest, Playwright e Storybook
├── content/corpus/     documentos fictícios do hospital usados nas respostas
├── evals/              conjunto de avaliação das respostas públicas
├── ops/                configuração de Prometheus e Grafana
├── docs/
│   ├── sdd.md          especificação (seções em docs/sdd/)
│   ├── plano-de-acao.md  etapas de implementação e status
│   ├── adr/            registros de decisão de arquitetura
│   └── privacy/        RIPD, ROPA, LIA e plano de incidentes
└── docker-compose.yml  ambiente completo opcional
```

## Rodar localmente

### Pré-requisitos

- Python 3.12 e [uv](https://docs.astral.sh/uv/)
- Node.js e [pnpm](https://pnpm.io/)
- Um PostgreSQL com a extensão `vector` (o ambiente `development` da Railway, ou o Docker abaixo)
- Opcional: uma chave do Gemini. Sem ela, use o adaptador `fake`.

### API

A API roda direto na máquina. Docker não é necessário.

1. Entre em `apps/api`.
2. Copie `.env.example` para `.env` e preencha `DATABASE_URL` com a URL pública do ambiente `development`. O `.env` não vai para o Git.
3. Instale as dependências com `uv sync`.
4. Aplique as migrações com `uv run alembic upgrade head`.
5. Suba a API com `uv run uvicorn app.main:app --reload`.
6. Abra `http://127.0.0.1:8000/health` e `http://127.0.0.1:8000/ready`. `/health` responde 200 sem o banco. `/ready` responde 200 quando o banco responde e a extensão `vector` está instalada.

### Frontend

1. Entre em `apps/web`.
2. Instale as dependências com `pnpm install`.
3. Suba com `pnpm dev` e abra `http://localhost:5173`. O Vite encaminha `/backend` para a API.

### Tudo em Docker

Alternativa ao banco da Railway: o `docker-compose.yml` da raiz sobe PostgreSQL com pgvector, API, frontend, Prometheus e Grafana, com dados e senhas só de desenvolvimento.

```bash
docker compose up --build
```

A API aplica as migrações, cria o admin e carrega o corpus antes de aceitar pedidos. O adaptador de IA é `fake`, então não precisa de chave. Ele não tem roteiro para o cadastro por conversa, então ali cada mensagem responde 503 e a tela mostra o aviso de indisponível; o formulário funciona. Para usar o Gemini, crie um `.env` na raiz com `APP_AI_ADAPTER=gemini` e `GEMINI_API_KEY`. O mesmo `.env` define o admin com `ADMIN_EMAIL` e `ADMIN_PASSWORD`; sem eles, vale `admin@example.com` / `Atrium-local-2026-admin`. O admin só é criado quando o banco não tem nenhum, então trocar essas variáveis depois exige `docker compose down -v` (ou remover o admin antigo).

| Serviço | Endereço | Acesso |
|---|---|---|
| Frontend | http://localhost:5173 | |
| API | http://127.0.0.1:8000 (`/health`, `/ready`) | admin de `ADMIN_EMAIL` (padrão `admin@example.com`) |
| Prometheus | http://localhost:9090 | |
| Grafana | http://localhost:3000 | `admin` / `admin` |
| PostgreSQL | `postgresql://atrium:atrium@127.0.0.1:5432/atrium` | |

`/metrics` pede o token `local-metrics-token`. Com esse banco local, `uv run pytest` em `apps/api` também roda os testes de integração. `docker compose down` para tudo e mantém os dados; `docker compose down -v` apaga os volumes.

A retenção da seção 11.6 roda com `uv run python -m app.scripts.retention`, em `apps/api`. Ela imprime quantas linhas cada regra apagou.

## Testes e qualidade

Os testes automáticos nunca chamam o Gemini nem o LangSmith. Eles usam `FakeChatProvider`, `DeterministicEmbeddingProvider` e `NoopFeedbackSink`.

```bash
# apps/api
uv run ruff check && uv run mypy && uv run pytest
```

```bash
# apps/web
pnpm exec eslint . && pnpm test
pnpm exec tsc --noEmit -p tsconfig.app.json && pnpm exec tsc --noEmit -p tsconfig.node.json
pnpm build && pnpm build-storybook
pnpm exec playwright test
```

A [CI](.github/workflows/ci.yml) roda tudo isso e confere que os tipos do frontend batem com o OpenAPI da API. A qualidade das respostas é medida com o conjunto em [`evals/`](evals/README.md).

## Contribuir

Contribuições são bem-vindas: correções, testes, acessibilidade, documentação, novas avaliações ou ideias de produto.

1. Leia o [guia de contribuição](CONTRIBUTING.md).
2. Procure uma issue aberta ou abra uma descrevendo o problema ou a proposta.
3. Crie uma branch `tipo/assunto-curto`, faça commits atômicos (`feat: …`, `fix: …`, `docs: …`) e abra a PR.

A especificação vem antes do código: se a mudança altera comportamento, a PR atualiza a seção correspondente do [SDD](docs/sdd.md).

## Licença

Distribuído sob a licença [MIT](LICENSE). Você pode usar, copiar, modificar e distribuir o código, mantendo o aviso de copyright.

<div align="center">
<br />
<sub>Feito com cuidado para mostrar que IA no atendimento pode ser útil, segura e honesta.</sub>
</div>
