"""Adaptadores de relógio, hash e segredo de sessão.

Também as implementações das portas de `app.ports` (seções 6.2 e 17): o Gemini para chat e
embedding, os falsos dos testes, o modo `demo`, os provedores sem chave, o LangSmith, a
extração de texto e o circuit breaker. A escolha pelo `APP_AI_ADAPTER` fica em `chat_factory`
e `embedding_factory`. O mapa dos arquivos está no `README.md`.
"""
