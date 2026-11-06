# ADR-013 — Serviços da Railway configurados pela API, com a API pelo Dockerfile

## Contexto

A seção 22.1 previa a configuração do serviço `api` em `apps/api/railway.json`, construído com Railpack. Na Etapa 10.1, a Railway já tinha descontinuado o Config as Code: serviços novos não aceitam `railway.json` e o arquivo deixa de valer em 2026-12-01. O substituto é Infraestrutura como Código em `.railway/railway.ts`, aplicada pela CLI com um token.

A semente lê `content/corpus`, que fica fora de `apps/api`. Um build com raiz em `apps/api` não enxerga o corpus.

## Decisão

Os serviços da Railway são configurados pela API da Railway, como no painel, e a tabela da seção 22.1 é a referência da configuração. A `api` e o `retention-job` são construídos pelo `apps/api/Dockerfile`, com o repositório inteiro como contexto. O mesmo Dockerfile serve ao `docker-compose.yml` local.

## Consequências

- A imagem que roda localmente é a mesma da Railway.
- Uma mudança de configuração na Railway atualiza a seção 22.1 na mesma mudança, porque não há arquivo que a imponha.
- Os `railway.json` de `ops/` saíram do repositório, porque não valiam para os serviços novos.

## Alternativas

- `railway.json`: descontinuado e recusado em serviços novos.
- Railpack com raiz em `apps/api`: não alcança `content/corpus`.
- `.railway/railway.ts`: fica para quando o pipeline aplicar a infraestrutura. Hoje ela exigiria um segundo caminho de deploy além do `railway up`.
