# Roteiro de rollback

Etapa 10.2 do [plano de ação](plano-de-acao.md) e seção 22.3 do SDD. Este roteiro volta a API e o frontend de produção à versão anterior **sem voltar o banco**. O banco não volta porque as migrações seguem expand and contract (seção 22.1): uma migração nunca quebra a versão anterior do código.

## Quando usar

Use quando uma versão nova está no ar e algo grave aparece: a fumaça falha, os alertas do Grafana disparam ou uma jornada quebra. Se o problema for só no frontend, volte só a Vercel. Se for só na API, volte só a Railway.

## Antes de começar

1. Anote o que está no ar agora, para saber voltar:
   - **API:** `curl -s https://atrium-gold.vercel.app/backend/health` devolve `build` com o commit em execução.
   - **Frontend:** `curl -s https://atrium-gold.vercel.app/ | grep -o 'assets/index-[^"]*'` mostra o arquivo de entrada da versão no ar.
2. Confira se a versão nova trouxe migração: `git diff --stat <commit anterior> <commit novo> -- apps/api/migrations`.
   - **Sem migração:** siga o roteiro.
   - **Com migração:** o rollback da API falha no pré-deploy. O `alembic upgrade head` da versão anterior não conhece a revisão nova do banco e para, e a Railway mantém a versão nova no ar. Nesse caso, a saída é corrigir para frente com uma nova PR. A Vercel pode voltar normalmente.

## Voltar a API (Railway)

**Pelo painel.** Projeto `atrium`, ambiente `production`, serviço `api`, aba Deployments. No deployment anterior, abra o menu de três pontos e escolha **Rollback**.

**Pela API da Railway,** como no teste abaixo: um redeploy com o id do deployment anterior. O `railway redeploy` da CLI não serve aqui, porque ele refaz só o deployment mais recente.

O rollback refaz a imagem daquele deployment e roda o pré-deploy de novo: migrações, admin e semente, que são idempotentes. O banco continua como está. A troca só acontece quando o `/ready` da versão anterior passa. Até lá, a versão atual segue no ar.

**Conferir.**

```bash
curl -s https://atrium-gold.vercel.app/backend/health
```

O `build` volta ao commit anterior. Um deploy pelo `deploy.yml` grava o commit em `app/BUILD_SHA`, e um deploy pelo repositório usa o `RAILWAY_GIT_COMMIT_SHA` da Railway.

## Voltar o frontend (Vercel)

**Pelo painel.** Projeto `atrium`, aba Deployments. No deployment de produção anterior, abra o menu e escolha **Instant Rollback**.

**Pela CLI.**

```bash
vercel rollback <url-da-implantação-anterior> --token "$VERCEL_TOKEN"
```

O Instant Rollback não refaz o build: ele só aponta `atrium-gold.vercel.app` para a implantação anterior, e a troca leva segundos.

**Conferir.**

```bash
curl -s https://atrium-gold.vercel.app/ | grep -o 'assets/index-[^"]*'
```

O arquivo de entrada volta ao da versão anterior.

**Atenção.** Depois de um rollback, a Vercel desliga a troca automática do domínio de produção. Uma implantação nova com `--prod`, inclusive a do `deploy.yml`, não recebe `atrium-gold.vercel.app` até alguém promover uma implantação. Quando a correção estiver pronta, promova:

```bash
vercel promote <url-da-implantação-corrigida> --token "$VERCEL_TOKEN"
```

## Voltar para a versão nova

Depois de corrigir, ou ao fim de um teste:

- **API:** no painel, faça **Redeploy** do deployment novo, ou publique a correção pelo `deploy.yml`.
- **Frontend:** `vercel promote` da implantação nova, que também religa a troca automática do domínio.

Rode a fumaça no fim:

```bash
node .github/scripts/smoke.mjs https://atrium-gold.vercel.app
```

## Teste do roteiro

Teste feito em 2026-11-06, entre a versão `14b346c` (Etapa 10.1) e a `a89a0d1` (Etapa 9.1), sem migração entre as duas.

| Passo | API (Railway) | Frontend (Vercel) | Resultado |
|---|---|---|---|
| Versão nova no ar | Deployment `f68abad4`, commit `a89a0d1` | Implantação `dpl_EjigQ6gkCWXDkwMY74CZFT4ceT2X`, entrada `index-D_M07svq.js` com 22 `modulepreload` | No ar |
| Rollback | Redeploy do deployment `df42e9c8`, commit `14b346c`, pela API da Railway | Instant Rollback para `dpl_33YwfS1PHRy9L3y3fZEbfdVWpBHj` | A API trocou em 40 s, depois de o `/ready` passar. O frontend trocou em segundos |
| Versão anterior no ar | Deployment `4ee7b9cf`, commit `14b346c`, e o `f68abad4` fora do ar | Entrada `index-DXo-m7oo.js` com 4 `modulepreload` | Fumaça verde na versão anterior |
| Banco | O pré-deploy não rodou nenhuma migração e encontrou o admin que já existia | | Nada voltou no banco |
| Volta para a versão nova | Redeploy do `f68abad4`, que virou o deployment `8c728eee`, commit `a89a0d1` | `promote` da `dpl_EjigQ6gkCWXDkwMY74CZFT4ceT2X` | Fumaça verde de novo |

Nesse teste, as duas versões da API tinham `build` nulo no `/health`, porque o código delas ainda não lia o `RAILWAY_GIT_COMMIT_SHA`. Por isso a conferência foi pela lista de deployments da Railway. Da Etapa 10.2 em diante, o `/health` mostra o commit também nos deploys pelo repositório.
