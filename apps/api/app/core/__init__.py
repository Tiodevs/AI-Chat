"""Configuração, logging, erros HTTP e raiz de composição.

Núcleo da API, a camada de infraestrutura da seção 6.2 do SDD. Não tem caso de uso: serve a
`app/main.py`, aos controladores, aos serviços, aos workflows e aos scripts. Também guarda os
middlewares, os cookies, as métricas, os spans e o formato SSE. O mapa dos arquivos está no
`README.md` desta pasta.
"""
