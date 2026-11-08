# ADR-001 — SPA React com Vite e rewrite

## Contexto

O navegador precisa falar só com a origem do frontend. Vercel e Railway são sites diferentes. A mesma origem mantém o cookie de sessão primário e dispensa CORS no tráfego normal. A seção 6.1 e a seção 13.4 do SDD descrevem esse desenho.

## Decisão

SPA React com Vite na Vercel, com rewrite de `/backend` para a API.

## Consequências

Sem servidor de frontend para manter. O fluxo SSE pelo rewrite precisa do teste de fumaça. A API continua pública na Railway, então o rewrite de `/backend` manda o cabeçalho `x-atrium-edge` com um segredo que a API exige em `/v1` (seção 10.3, Etapa 12.5).

## Alternativas

Next.js com rota de proxy. API em subdomínio próprio com cookie de domínio.
