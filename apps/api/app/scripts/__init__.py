"""Comandos de operação. Não rodam na inicialização da API.

Cada módulo roda com `python -m app.scripts.<nome>`, dentro de `apps/api`: semente, busca,
pergunta, admin, retenção, avaliação e exportação do OpenAPI (seção 6.3). O pré-deploy da
Railway roda `bootstrap_admin` e `seed`, e o `retention-job` roda `retention` (seção 22.1). O
mapa dos comandos está no `README.md`.
"""
