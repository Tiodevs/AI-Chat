"""Controladores HTTP. Interpretam o pedido e chamam um serviço.

Camada de controle da seção 6.2 do SDD; o contrato das rotas está na seção 12. Cada módulo
expõe um `APIRouter` que `app/main.py` inclui. Um controlador lê o corpo (schema de
`app.schemas`), os cookies e os cabeçalhos, chama um método de serviço e converte o resultado
no schema de resposta. Ele não importa SQLAlchemy, LangChain, LangGraph, LangSmith nem
`app.repositories`, e não monta erro: o erro de domínio sobe até `app.core.errors`. O teste de
`tests/architecture` confere os imports. A tabela das rotas está no `README.md` desta pasta.
"""
