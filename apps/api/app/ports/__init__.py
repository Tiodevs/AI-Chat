"""Protocolos dos adaptadores. Seção 6.2 do SDD.

Camada de infraestrutura, a metade "porta" do padrão portas e adaptadores. Um `Protocol` do
Python descreve os métodos que um objeto precisa ter, sem exigir herança: qualquer classe com a
mesma forma serve, e o mypy confere a forma. Assim o serviço e o workflow dependem da porta, e
a raiz de composição (`app/core/container.py`) escolhe o adaptador: o Gemini em produção, o
falso nos testes, o `demo` na e2e. Por isso os testes trocam o provedor sem mudar o caso de
uso (seção 17).

Os adaptadores ficam em `app/adapters`. Duas portas são implementadas em `app/services`:
`TokenBudget`, por `PostgresTokenBudget`, e `HybridSearch`, por `RetrievalService`.
"""
