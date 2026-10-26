# Atrium

Assistente público para visitantes do hospital fictício Harborlight General Hospital.

A especificação pronta para implementação está em [docs/sdd.md](docs/sdd.md).

A implementação segue o [plano de ação](docs/plano-de-acao.md), em etapas com critérios de aceite e aprovação a cada entrega.

## Como rodar localmente

A API roda direto na máquina. Docker não é necessário.

1. Entre em `apps/api`.
2. Se quiser sobrescrever os padrões, copie `.env.example` para `.env`. O `.env` não vai para o Git.
3. Instale as dependências com `uv sync`.
4. Suba a API com `uv run uvicorn app.main:app --reload`.
5. Abra `http://127.0.0.1:8000/health`. A resposta é 200 e traz o cabeçalho `x-request-id`.

O frontend entra na Etapa 1.3. O banco da Railway entra na Etapa 2.1.
