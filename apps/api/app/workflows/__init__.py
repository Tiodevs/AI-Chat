"""LangChain e LangGraph. Sem FastAPI e sem sessão SQLAlchemy. Seção 6.2 do SDD.

Camada de workflow de IA: o pipeline de perguntas (`qa`, seção 7.1) e o grafo do cadastro
(`registration`, seção 7.2). Os workflows recebem as portas pelo construtor e nascem uma vez
por processo, no `AiRuntime` de `app.core.container`. O mapa dos arquivos está no `README.md`.
"""
