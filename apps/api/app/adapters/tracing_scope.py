"""Desliga o rastro automático em volta da chamada ao modelo. Seção 18.4.

Adaptador auxiliar do `GeminiChatProvider`. A cada chamada, o LangChain consulta o contexto de
rastro do LangSmith para decidir se anexa o tracer que grava o run automaticamente. Com o
contexto desligado, o prompt cru, que pode ter dado de saúde, nunca vira um run. O que vai ao
LangSmith é só o rastro explícito que os workflows gravam com a política de cada passo.
"""

from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def quiet_provider_tracing() -> Iterator[None]:
    """O prompt cru não vira um run do LangChain. O rastro explícito vem depois.

    `tracing_context(enabled=False)` vale para o bloco inteiro e devolve o contexto anterior
    na saída. O import do `langsmith` fica aqui dentro, para carregar só no primeiro uso.
    """
    from langsmith import tracing_context

    with tracing_context(enabled=False):
        yield
