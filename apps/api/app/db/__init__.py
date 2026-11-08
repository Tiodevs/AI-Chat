"""Sessão assíncrona e unidade de trabalho. Seção 6.4 do SDD.

Camada de persistência, entre o serviço e o repositório (seção 6.2). Os serviços abrem a
sessão e a transação daqui; o `app/main.py` abre e fecha o pool; o `alembic/env.py` e a
semente criam o engine. O mapa dos arquivos está no `README.md` desta pasta.
"""
