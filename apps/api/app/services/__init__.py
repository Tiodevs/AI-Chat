"""Camada de serviços da API: um caso de uso por método público. Seção 6.2 do SDD.

Os serviços ficam entre os controladores (`app/controllers`) e o resto do "M" do MVC:
domínio, workflows de IA e repositórios. Cada método abre e fecha as próprias transações
curtas com `open_session` e `UnitOfWork` (`app/db`), e decide ali a autorização de dono, o
limite de taxa, o orçamento de tokens, a idempotência e a auditoria. A autorização de admin
é conferida antes, no controlador, por `controllers/admin_guard.py`.

Nenhuma chamada ao Gemini, ao embedding ou ao LangSmith corre com transação aberta
(seção 6.4). A camada não importa FastAPI, LangChain, LangGraph nem LangSmith, e o teste de
`tests/architecture` falha se isso mudar. O mapa dos arquivos está no `README.md` da pasta.
"""
