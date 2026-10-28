"""Desliga o rastro automático em volta da chamada ao modelo. Seção 18.4."""

from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def quiet_provider_tracing() -> Iterator[None]:
    """O prompt cru não vira um run do LangChain. O rastro explícito vem depois."""
    from langsmith import tracing_context

    with tracing_context(enabled=False):
        yield
