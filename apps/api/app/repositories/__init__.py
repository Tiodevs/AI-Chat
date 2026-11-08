"""Consultas. Sem construção de prompt. Seção 6.2 do SDD.

Camada de repositório. Cada repositório recebe a `AsyncSession` que o serviço abriu dentro de
uma `UnitOfWork` e só consulta e grava. Quem abre e fecha a transação é o serviço (seção 6.4),
então nenhum repositório faz commit. A exceção é o `SeedLock`, que trabalha numa conexão
própria. Os serviços de `app.services` criam os repositórios a cada transação. As tabelas estão
em `app.models` e na seção 8 do SDD. O teste de arquitetura proíbe aqui LangChain, LangGraph,
LangSmith e FastAPI.
"""
