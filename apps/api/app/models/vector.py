"""Tipo de coluna `vector(768)` do pgvector, declarado sem o pacote `pgvector` do Python.

Camada de entidade de persistência (seção 6.2 do SDD). `Chunk.embedding` e a migração
`0002_corpus` usam `Vector`. Os adaptadores de embedding (`gemini_embedding`,
`deterministic_embedding` e `lexical_embedding`) usam `EMBEDDING_DIMENSIONS` como dimensão
padrão. Seções 8.1 e 8.3 do SDD.
"""

from typing import Any

from sqlalchemy.types import UserDefinedType

# Dimensão do vetor na versão 1 (seção 8.3). O `/ready` compara o tipo real da coluna com
# `EMBEDDING_DIMENSIONS` da configuração e falha quando diferem (NFR-9). Mudar a dimensão pede
# uma migração nova e um re-embedding completo: a `0002_corpus` importa esta constante.
EMBEDDING_DIMENSIONS = 768


class Vector(UserDefinedType[list[float]]):
    """Tipo `vector(n)` do pgvector, só para o DDL.

    O tipo não converte valores na ida nem na volta. Por isso os repositórios mandam o vetor
    como texto, com `vector_literal`, e convertem no SQL com `CAST(:embedding AS vector)`.
    """

    # Diz ao SQLAlchemy que o tipo pode entrar no cache de SQL compilado. Sem isso, ele emite
    # um aviso e não guarda em cache o SQL que usa o tipo.
    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        """Guarda a dimensão que o DDL vai declarar."""
        super().__init__()
        self.dimensions = dimensions

    def get_col_spec(self, **kw: Any) -> str:
        """Texto do tipo no `CREATE TABLE`, por exemplo `vector(768)`."""
        return f"vector({self.dimensions})"
